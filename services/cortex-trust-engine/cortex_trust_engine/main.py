from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager, suppress
from typing import Any
from pathlib import Path

try:
    import structlog
except ImportError:  # pragma: no cover - optional in unit-test environments
    import logging

    class _StructlogFallback:
        @staticmethod
        def get_logger():
            return logging.getLogger("cortex-trust-engine")

    structlog = _StructlogFallback()
from fastapi import FastAPI, HTTPException, Request, Response

try:
    import nats
except ImportError:  # pragma: no cover - optional in unit-test environments
    nats = None

from cortex_core.contracts import ActionClass, ResponseEligibility, RiskEnvelope, SOTRecord, SecurityEvidence  # noqa: E402
from cortex_core.sot import (  # noqa: E402
    evaluate_sot_impact,
    expire_sot as expire_sot_record,
    issue_sot as issue_sot_record,
    revoke_sot as revoke_sot_record,
)
from cortex_trust_engine.models import (  # noqa: E402
    ThreatLevel,
    TrustEvaluateV2Response,
    TrustEvaluationRequest,
    TrustEvaluationResponse,
)
from cortex_trust_engine.scorer import (  # noqa: E402
    compute_score,
    make_decision,
    response_eligibility_for,
    score_evidences,
    threat_level_for,
)

log = structlog.get_logger()

profiles: dict[str, dict[str, Any]] = {}
sot_records: dict[str, dict[str, Any]] = {}
nats_client: Any | None = None
nats_js = None
JETSTREAM_SUBJECTS = [
    "cortex.trust.updates",
    "cortex.trust.decisions",
    "cortex.obs.sot.issued",
    "cortex.agents.tasks.remediation",
]


def require_internal_api(request: Request) -> None:
    expected = os.getenv("CORTEX_INTERNAL_API_TOKEN", "").strip()
    if not expected:
        return
    if request.headers.get("x-cortex-internal-token", "") != expected:
        raise HTTPException(status_code=403, detail="internal_api_auth_required")


def edge_inference_enabled() -> bool:
    return os.getenv("EDGE_INFERENCE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


async def _load_or_create_profile(entity_id: str, entity_type: str) -> dict[str, Any]:
    return profiles.setdefault(
        entity_id,
        {
            "entity_type": entity_type,
            "score": 85.0,
            "threat_level": ThreatLevel.LOW.value,
            "response_eligibility": ResponseEligibility.NONE.value,
            "updated_at": time.time(),
        },
    )


async def _save_profile(entity_id: str, profile: dict[str, Any]) -> None:
    profile["updated_at"] = time.time()
    profiles[entity_id] = profile


async def _ensure_stream() -> None:
    if nats_js is None:
        return
    try:
        await nats_js.stream_info("CORTEX_EVENTS")
    except Exception:
        with suppress(Exception):
            await nats_js.add_stream(name="CORTEX_EVENTS", subjects=JETSTREAM_SUBJECTS)


async def _publish(subject: str, payload: dict[str, Any]) -> None:
    if nats_client is None:
        return
    encoded = json.dumps(payload).encode()
    if nats_js is not None:
        try:
            await nats_js.publish(subject, encoded)
            return
        except Exception as exc:
            log.warning("trust.publish.jetstream_failed", subject=subject, error=str(exc)[:200])
    with suppress(Exception):
        await nats_client.publish(subject, encoded)


async def _subscribe(subject: str, cb, durable: str) -> None:
    if nats_client is None:
        return
    if nats_js is not None:
        try:
            await nats_js.subscribe(subject, cb=cb, durable=durable)
            return
        except Exception as exc:
            log.warning("trust.subscribe.jetstream_failed", subject=subject, error=str(exc)[:200])
    await nats_client.subscribe(subject, cb=cb)


async def _internal_evaluate(body: dict[str, Any]) -> dict[str, Any]:
    entity_id = body["entity_id"]
    evidences = [
        SecurityEvidence.model_validate(ev)
        for ev in body.get("evidences", [])
        if edge_inference_enabled() or ev.get("source") != "edge_inference"
    ]
    profile = await _load_or_create_profile(entity_id, body.get("entity_type", "machine"))
    new_score, distinct_sources, strong_signals = score_evidences(
        base_score=float(profile["score"]),
        evidences=evidences,
        criticality=body.get("resource_context", body.get("criticality", "normal")),
    )
    envelope = RiskEnvelope(
        entity_id=entity_id,
        entity_type=body.get("entity_type", "machine"),
        action=body.get("action", "trust_evaluate"),
        action_class=ActionClass.ADVISORY,
        trust_score=new_score,
        threat_level=5 if new_score < 20 else 4 if new_score < 40 else 2 if new_score < 70 else 1,
        evidence_count=len(evidences),
        strong_signal_count=strong_signals,
        distinct_sources=distinct_sources,
        blast_radius=int(body.get("blast_radius", 0)),
        crown_jewels_exposed=bool(body.get("crown_jewels_exposed", False)),
        criticality=body.get("criticality", "normal"),
        scopes=list(body.get("scopes", [])),
        environment=body.get("environment", "preprod"),
    )
    profile["score"] = new_score
    profile["threat_level"] = threat_level_for(new_score, strong_signals).value
    profile["response_eligibility"] = response_eligibility_for(envelope).value
    await _save_profile(entity_id, profile)
    await _publish(
        "cortex.trust.decisions",
        {
            "entity_id": entity_id,
            "score_after": profile["score"],
            "threat_level": profile["threat_level"],
            "response_eligibility": profile["response_eligibility"],
            "timestamp": time.time(),
        },
    )
    if profile["score"] < 55.0 and profile["response_eligibility"] in {
        ResponseEligibility.REVERSIBLE_ONLY.value,
        ResponseEligibility.APPROVAL_GATED.value,
    }:
        await _publish(
            "cortex.agents.tasks.remediation",
            {
                "task_id": f"sot-{entity_id}-{int(time.time())}",
                "type": "prepare_issue_sot",
                "entity_id": entity_id,
                "score": profile["score"],
                "reasons": [
                    ev.signal_type
                    for ev in evidences
                    if ev.severity > 0.5
                ],
                "execution_mode": "prepare",
            },
        )
    return {
        "entity_id": entity_id,
        "score_after": profile["score"],
        "threat_level": profile["threat_level"],
        "response_eligibility": profile["response_eligibility"],
        "evidence_count": len(evidences),
        "distinct_sources": distinct_sources,
        "strong_signals": strong_signals,
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    global nats_client, nats_js
    if nats is None:
        log.warning("trust.startup.nats_missing")
        yield
        return

    with suppress(Exception):
        nats_client = await nats.connect("nats://cortex-nats:4222")
        nats_js = nats_client.jetstream()
        await _ensure_stream()

        async def on_trust_update(msg) -> None:
            try:
                data = json.loads(msg.data)
                if data.get("evidences"):
                    await _internal_evaluate(data)
            except Exception as exc:
                log.error("trust.consumer.error", error=str(exc))
            finally:
                if hasattr(msg, "ack"):
                    await msg.ack()

        await _subscribe("cortex.trust.updates", on_trust_update, "trust-engine-update-consumer")

    try:
        yield
    finally:
        if nats_client is not None:
            with suppress(Exception):
                await nats_client.drain()
        nats_client = None
        nats_js = None


app = FastAPI(title="Cortex Trust Engine", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "cortex-trust-engine", "edge_inference_enabled": edge_inference_enabled()}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live", "service": "cortex-trust-engine"}


@app.get("/health/startup")
async def health_startup() -> dict[str, str]:
    return {"status": "started", "service": "cortex-trust-engine"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    return {"status": "ready", "service": "cortex-trust-engine"}


@app.get("/metrics")
async def metrics() -> Response:
    body = "\n".join(
        [
            "# HELP cortex_trust_engine_profiles Number of cached trust profiles.",
            "# TYPE cortex_trust_engine_profiles gauge",
            f"cortex_trust_engine_profiles {len(profiles)}",
            "# HELP cortex_trust_engine_sot_records Number of cached SOT records.",
            "# TYPE cortex_trust_engine_sot_records gauge",
            f"cortex_trust_engine_sot_records {len(sot_records)}",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")


@app.get("/version")
async def version() -> dict[str, str]:
    return {"service": "cortex-trust-engine", "version": "0.1.0"}


@app.post("/v1/evaluate")
async def evaluate(req: TrustEvaluationRequest) -> TrustEvaluationResponse:
    score = compute_score(req.base_score, req.factors)
    return TrustEvaluationResponse(
        entity_id=req.entity_id,
        entity_type=req.entity_type,
        score=score,
        decision=make_decision(score),
        factors_applied=req.factors,
    )


@app.post("/trust/evaluate/v2")
async def evaluate_v2(request: Request) -> TrustEvaluateV2Response:
    require_internal_api(request)
    body = await request.json()
    result = await _internal_evaluate(body)
    return TrustEvaluateV2Response(
        entity_id=body["entity_id"],
        entity_type=body.get("entity_type", "machine"),
        trust_score=result["score_after"],
        threat_level=ThreatLevel(result["threat_level"]),
        response_eligibility=ResponseEligibility(result["response_eligibility"]),
        decision=make_decision(int(result["score_after"])),
        retained_evidence_count=len(body.get("evidences", [])),
        degraded=False,
        rationale=[
            "Trust evaluation completed from structured evidences.",
            f"distinct_sources={result['distinct_sources']}",
            f"strong_signals={result['strong_signals']}",
        ]
        + [
            f"edge_risk_signal:{evidence.get('signal_type')}"
            for evidence in body.get("evidences", [])
            if evidence.get("source") == "edge_inference"
        ],
    )


@app.post("/trust/sot/issue")
async def issue_sot_endpoint(request: Request) -> dict[str, Any]:
    require_internal_api(request)
    body = await request.json()
    sot = issue_sot_record(
        entity_id=body["entity_id"],
        entity_type=body.get("entity_type", "machine"),
        reason_codes=list(body.get("reasons", [])),
        observation_level=str(body.get("observation_level", "deep")),
        restrictions=list(body.get("restrictions", ["no_new_secrets", "no_crown_jewel_access", "limited_egress"])),
        ttl_seconds=int(body.get("ttl_seconds", 1800)),
        renewable=bool(body.get("renewable", False)),
        metadata={"issued_by": "trust-engine", "score": body.get("score")},
    )
    sot_records[sot.token_id] = sot.model_dump()
    await _publish("cortex.obs.sot.issued", {**sot.model_dump(), "timestamp": time.time()})
    return sot.model_dump()


@app.post("/trust/sot/{token_id}/expire")
async def expire_sot_endpoint(token_id: str, request: Request) -> dict[str, Any]:
    require_internal_api(request)
    record = sot_records.get(token_id)
    if not record:
        return {"error": "sot_not_found", "token_id": token_id}
    sot = SOTRecord.model_validate(record)
    sot = expire_sot_record(sot)
    sot_records[token_id] = sot.model_dump()
    await _publish("cortex.obs.sot.issued", {**sot.model_dump(), "event": "expired", "timestamp": time.time()})
    return sot.model_dump()


@app.post("/trust/sot/{token_id}/revoke")
async def revoke_sot_endpoint(token_id: str, request: Request) -> dict[str, Any]:
    require_internal_api(request)
    record = sot_records.get(token_id)
    if not record:
        return {"error": "sot_not_found", "token_id": token_id}
    body = await request.json()
    sot = SOTRecord.model_validate(record)
    sot = revoke_sot_record(sot, str(body.get("reason", "manual_revoke")))
    sot_records[token_id] = sot.model_dump()
    await _publish("cortex.obs.sot.issued", {**sot.model_dump(), "event": "revoked", "timestamp": time.time()})
    return sot.model_dump()


@app.post("/trust/sot/{token_id}/impact")
async def evaluate_sot_impact_endpoint(token_id: str, request: Request) -> dict[str, Any]:
    require_internal_api(request)
    record = sot_records.get(token_id)
    if not record:
        return {"error": "sot_not_found", "token_id": token_id}
    sot = SOTRecord.model_validate(record)
    return evaluate_sot_impact(sot)


@app.get("/trust/sot/{token_id}")
async def get_sot(token_id: str, request: Request) -> dict[str, Any]:
    require_internal_api(request)
    record = sot_records.get(token_id)
    if not record:
        return {"error": "sot_not_found", "token_id": token_id}
    return record


@app.get("/trust/profile/{entity_id}")
async def get_profile(entity_id: str, request: Request) -> dict[str, Any]:
    require_internal_api(request)
    profile = await _load_or_create_profile(entity_id, "machine")
    return {"entity_id": entity_id, **profile}
