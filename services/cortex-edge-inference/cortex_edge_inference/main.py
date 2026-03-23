from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Response

from cortex_core.contracts import SecurityEvidence  # noqa: E402

from .config import EdgeInferenceConfig
from .metrics import EdgeMetrics
from .models import EdgeInferenceRequest, EdgeInferenceResponse, EdgeRiskSignal, EvidenceItem


class AppState:
    def __init__(self, config: EdgeInferenceConfig):
        self.config = config
        self.metrics = EdgeMetrics()
        self.started_at = time.time()
        self.startup_complete = False


def _headers(config: EdgeInferenceConfig, trace_id: str, correlation_id: str | None) -> dict[str, str]:
    headers = {"x-cortex-trace-id": trace_id}
    if correlation_id:
        headers["x-cortex-correlation-id"] = correlation_id
    if config.internal_api_token:
        headers["x-cortex-internal-token"] = config.internal_api_token
    return headers


def _route_hint(score: float) -> str:
    if score >= 80:
        return "sentinel_immediate_attention"
    if score >= 60:
        return "deep_graph_reasoning"
    if score >= 35:
        return "hybrid_analysis"
    return "fast_path"


def infer_edge_risk(req: EdgeInferenceRequest, config: EdgeInferenceConfig) -> EdgeRiskSignal:
    evidence: list[EvidenceItem] = []
    score = 0.0

    if req.context.ip_reputation >= 70:
        score += 24.0
        evidence.append(EvidenceItem(code="ip_reputation_high", detail="IP reputation indicates elevated ingress risk.", weight=0.24))
    elif req.context.ip_reputation >= 40:
        score += 12.0
        evidence.append(EvidenceItem(code="ip_reputation_medium", detail="IP reputation is unusual for this identity.", weight=0.12))

    if req.context.geo_consistency < 0.4:
        score += 18.0
        evidence.append(EvidenceItem(code="geo_inconsistency", detail="Session geolocation chain is inconsistent with historical sessions.", weight=0.18))

    if not req.context.device_fingerprint_present:
        score += 16.0
        evidence.append(EvidenceItem(code="fingerprint_missing", detail="No stable device fingerprint is attached to this session.", weight=0.16))

    if req.context.path_anomaly_score >= 65:
        score += 16.0
        evidence.append(EvidenceItem(code="path_anomaly_high", detail="Network path deviates strongly from previous session chains.", weight=0.16))
    elif req.context.path_anomaly_score >= 35:
        score += 8.0
        evidence.append(EvidenceItem(code="path_anomaly_medium", detail="Network path is rarer than baseline.", weight=0.08))

    if req.context.auth_context_score < 50:
        score += 10.0
        evidence.append(EvidenceItem(code="auth_context_weak", detail="Authentication context is weaker than the baseline for this access.", weight=0.10))

    if req.context.previous_session_chain_score < 50:
        score += 8.0
        evidence.append(EvidenceItem(code="session_chain_break", detail="Previous session chain does not support the current ingress path.", weight=0.08))

    if req.context.transport_risk >= 60:
        score += 10.0
        evidence.append(EvidenceItem(code="transport_suspect", detail="Transport characteristics are suspicious for this session.", weight=0.10))

    if req.context.vpn_or_proxy_detected:
        score += 8.0
        evidence.append(EvidenceItem(code="vpn_or_proxy", detail="VPN, proxy, or relay hints are present on ingress.", weight=0.08))

    if req.context.related_anomalous_sessions > 0:
        related_weight = min(10.0, req.context.related_anomalous_sessions * 2.5)
        score += related_weight
        evidence.append(EvidenceItem(code="related_anomalous_sessions", detail="This session is correlated with other anomalous sessions.", weight=round(related_weight / 100.0, 2)))

    if req.context.asn_risk >= 50:
        score += 6.0
        evidence.append(EvidenceItem(code="asn_risk", detail="Autonomous system usage is unusual for the identity.", weight=0.06))

    inferred_risk = max(0.0, min(100.0, round(score, 2)))
    confidence = min(0.95, round(0.35 + (len(evidence) * 0.08), 2))
    return EdgeRiskSignal(
        session_id=req.session_id,
        entity_id=req.entity_id,
        entity_type=req.entity_type,
        inferred_edge_risk=inferred_risk,
        confidence=confidence,
        evidence=evidence[: config.max_evidence_count],
        trace_id=req.trace_id,
        correlation_id=req.correlation_id,
        feature_flags={
            "EDGE_INFERENCE_ENABLED": config.enabled,
            "EDGE_INFERENCE_SHADOW_MODE": config.shadow_mode,
        },
        route_hint=_route_hint(inferred_risk),
    )


def _signal_to_evidence(req: EdgeInferenceRequest, signal: EdgeRiskSignal) -> SecurityEvidence:
    severity = min(1.0, signal.inferred_edge_risk / 100.0)
    metadata = {
        "session_id": req.session_id,
        "machine_id": req.machine_id,
        "tenant_id": req.tenant_id,
        "trace_id": signal.trace_id,
        "correlation_id": signal.correlation_id,
        "inferred": True,
        "route_hint": signal.route_hint,
        "evidence": [item.model_dump() for item in signal.evidence],
    }
    return SecurityEvidence(
        entity_id=req.entity_id,
        source="edge_inference",
        signal_type="edge_risk_inferred",
        severity=severity,
        confidence=signal.confidence,
        metadata=metadata,
        ttl=1800,
    )


async def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: float) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response


async def _check_dependency(base_url: str, timeout_seconds: float) -> bool:
    paths = ("/health/ready", "/readyz", "/health")
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for path in paths:
            try:
                response = await client.get(f"{base_url}{path}")
                if response.status_code == 200:
                    return True
            except httpx.HTTPError:
                continue
    return False


async def _audit_signal(state: AppState, req: EdgeInferenceRequest, signal: EdgeRiskSignal) -> None:
    if not state.config.audit_required:
        return
    state.metrics.audit_events_total += 1
    try:
        await _post_json(
            f"{state.config.audit_url}/v1/events",
            {
                "principal_id": state.config.service_name,
                "principal_type": "ai_agent",
                "event_type": "edge.risk_signal.inferred",
                "action": "infer_edge_risk",
                "decision": "recorded",
                "reason": f"edge_risk={signal.inferred_edge_risk}",
                "risk_level": min(5, max(1, int(signal.inferred_edge_risk // 20) + 1)),
                "metadata": {
                    "session_id": req.session_id,
                    "entity_id": req.entity_id,
                    "entity_type": req.entity_type,
                    "signal": signal.model_dump(),
                },
                "correlation_id": req.correlation_id or req.trace_id,
                "action_class": "advisory",
                "execution_mode": "prepare",
                "capability_maturity": "beta",
                "degraded_mode": False,
            },
            headers=_headers(state.config, req.trace_id, req.correlation_id),
            timeout_seconds=state.config.request_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        state.metrics.audit_failures_total += 1
        if state.config.audit_required:
            raise HTTPException(status_code=503, detail=f"audit_unavailable:{exc.__class__.__name__}") from exc


async def _forward_to_trust(state: AppState, req: EdgeInferenceRequest, signal: EdgeRiskSignal) -> dict[str, Any] | None:
    if not state.config.trust_forward_enabled:
        return None
    state.metrics.trust_forward_total += 1
    evidence = _signal_to_evidence(req, signal)
    try:
        response = await _post_json(
            f"{state.config.trust_engine_url}/trust/evaluate/v2",
            {
                "entity_id": req.entity_id,
                "entity_type": req.entity_type,
                "action": "edge_risk_evaluate",
                "criticality": req.context.asset_criticality,
                "resource_context": req.context.asset_criticality,
                "blast_radius": req.blast_radius,
                "crown_jewels_exposed": req.crown_jewels_exposed,
                "trace_id": req.trace_id,
                "correlation_id": req.correlation_id,
                "evidences": [evidence.model_dump()],
                "scopes": req.scopes,
            },
            headers=_headers(state.config, req.trace_id, req.correlation_id),
            timeout_seconds=state.config.request_timeout_seconds,
        )
        return response.json()
    except httpx.HTTPError as exc:
        state.metrics.trust_forward_failures_total += 1
        if state.config.trust_forward_required:
            raise HTTPException(status_code=503, detail=f"trust_engine_unavailable:{exc.__class__.__name__}") from exc
        return None


def create_app(config: EdgeInferenceConfig | None = None) -> FastAPI:
    cfg = config or EdgeInferenceConfig.load()
    state = AppState(cfg)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state.startup_complete = True
        yield

    app = FastAPI(
        title="Cortex Edge Inference",
        version=cfg.version,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.edge = state

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": cfg.service_name,
            "version": cfg.version,
            "enabled": cfg.enabled,
            "shadow_mode": cfg.shadow_mode,
        }

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live", "service": cfg.service_name}

    @app.get("/health/startup")
    async def health_startup(response: Response) -> dict[str, Any]:
        if not state.startup_complete:
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "started", "service": cfg.service_name}

    @app.get("/health/ready")
    async def health_ready(response: Response) -> dict[str, Any]:
        dependencies: dict[str, bool] = {}
        if cfg.audit_required:
            dependencies["audit"] = await _check_dependency(cfg.audit_url, cfg.request_timeout_seconds)
        if cfg.trust_forward_required:
            dependencies["trust_engine"] = await _check_dependency(cfg.trust_engine_url, cfg.request_timeout_seconds)
        ready = all(dependencies.values()) if dependencies else True
        if not ready:
            response.status_code = 503
        return {"status": "ready" if ready else "not_ready", "dependencies": dependencies}

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=state.metrics.render(), media_type="text/plain; version=0.0.4")

    @app.get("/version")
    async def version() -> dict[str, str]:
        return {"service": cfg.service_name, "version": cfg.version}

    @app.post("/v1/edge/infer", response_model=EdgeInferenceResponse)
    async def infer(req: EdgeInferenceRequest) -> EdgeInferenceResponse:
        if not cfg.enabled:
            raise HTTPException(status_code=503, detail="edge_inference_disabled")
        state.metrics.inference_requests_total += 1
        try:
            signal = infer_edge_risk(req, cfg)
            await _audit_signal(state, req, signal)
            trust_response = None if cfg.shadow_mode else await _forward_to_trust(state, req, signal)
            rationale = [
                "Edge inference emits an advisory risk signal only.",
                "Trust Engine remains the final scorer before Policy Engine evaluation.",
                "Ingress path is inferred from converging signals and never asserted as direct device visibility.",
            ]
            return EdgeInferenceResponse(
                signal=signal,
                trust_response=trust_response,
                degraded=trust_response is None and cfg.trust_forward_enabled,
                rationale=rationale,
            )
        except HTTPException:
            state.metrics.inference_failures_total += 1
            raise

    return app


app = create_app()
