import os
import json
import hmac
import hashlib
from pathlib import Path

import httpx
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field


class IntentRequest(BaseModel):
    request_id: str
    task: str
    payload: str
    risk_level: int = 1
    actions: list[str] = Field(default_factory=list)


class ModelCandidateRequest(BaseModel):
    model_id: str
    parent_model_id: str | None = None
    tenant_scope: str
    machine_scope: str
    class_scope: str
    training_window: str
    feature_schema_hash: str
    signed_manifest: dict[str, object]
    evaluation_report: dict[str, float] = Field(default_factory=dict)
    rollback_pointer: str | None = None
    parameters: dict[str, object] = Field(default_factory=dict)


app = FastAPI(title="Cortex Orchestrator")
model_registry: dict[str, dict[str, object]] = {}


def _append_model_audit(entry: dict[str, object]) -> None:
    path = os.getenv("CORTEX_ORCHESTRATOR_MODEL_AUDIT_LOG", "").strip()
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _verify_internal_token(token: str | None) -> bool:
    expected = os.getenv("CORTEX_INTERNAL_API_TOKEN", "cortex-internal-dev-token")
    return bool(token) and token == expected


def _verify_manifest(manifest: dict[str, object]) -> bool:
    algorithm = str(manifest.get("algorithm", ""))
    if algorithm != "hmac-sha256":
        return False
    body = manifest.get("body", {})
    if not isinstance(body, dict):
        return False
    signing_key = os.getenv("SENTINEL_MODEL_SIGNING_KEY", "sentinel-machine-dev-key-32-bytes!!").encode("utf-8")
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hmac.new(signing_key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(str(manifest.get("signature", "")), expected)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cortex-orchestrator"}


@app.post("/v1/model/promote")
async def promote_model(req: ModelCandidateRequest, x_cortex_internal_token: str | None = Header(default=None)) -> dict[str, object]:
    if not _verify_internal_token(x_cortex_internal_token):
        return {"accepted": False, "reason": "internal_api_auth_required"}
    if not _verify_manifest(req.signed_manifest):
        return {"accepted": False, "reason": "invalid_manifest_signature"}
    if req.signed_manifest.get("body", {}).get("feature_schema_hash") != req.feature_schema_hash:
        return {"accepted": False, "reason": "feature_schema_mismatch"}
    gain = float(req.evaluation_report.get("shadow_vs_champion_delta", 0.0))
    stability = float(req.evaluation_report.get("baseline_stability_score", 0.0))
    if gain <= 0 or stability < 0.6:
        mode = "shadow"
        promotion = False
    elif gain < 0.1:
        mode = "canary"
        promotion = False
    else:
        mode = "promote"
        promotion = True
    model_registry[req.model_id] = {
        "tenant_scope": req.tenant_scope,
        "machine_scope": req.machine_scope,
        "mode": mode,
        "rollback_pointer": req.rollback_pointer,
    }
    response = {
        "accepted": True,
        "model_id": req.model_id,
        "mode": mode,
        "promotion": promotion,
        "rollback_pointer": req.rollback_pointer,
    }
    _append_model_audit(
        {
            "event_type": "model_candidate_received",
            "model_id": req.model_id,
            "tenant_scope": req.tenant_scope,
            "machine_scope": req.machine_scope,
            "mode": mode,
            "promotion": promotion,
            "rollback_pointer": req.rollback_pointer,
        }
    )
    return response


@app.post("/v1/plan")
async def plan(req: IntentRequest) -> dict[str, object]:
    vllm_url = os.getenv("VLLM_URL", "http://cortex-vllm:8080")
    sentinel_url = os.getenv("SENTINEL_URL", "http://cortex-sentinel:8080")

    async with httpx.AsyncClient(timeout=5.0) as client:
        route_resp = await client.post(f"{vllm_url}/v1/route", json={"task": req.task, "payload": req.payload})
        route_resp.raise_for_status()
        validation_resp = await client.post(
            f"{sentinel_url}/v1/validate-plan",
            json={"plan_id": req.request_id, "risk_level": req.risk_level, "actions": req.actions},
        )
        validation_resp.raise_for_status()

    return {
        "plan_id": req.request_id,
        "route": route_resp.json(),
        "validation": validation_resp.json(),
    }


@app.post("/v1/decision")
async def decision(req: IntentRequest) -> dict[str, object]:
    mcp_url = os.getenv("MCP_URL", "http://cortex-mcp-server:8080")
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{mcp_url}/mcp/tools/call",
            json={
                "tool": "decision_analyze_response",
                "params": {
                    "task_id": req.request_id,
                    "entity_id": req.request_id,
                    "entity_type": "workflow",
                    "candidate_action": req.task,
                    "payload": req.payload,
                    "risk_level": req.risk_level,
                    "actions": req.actions,
                },
                "agent_id": "orchestrator",
                "agent_scopes": ["admin:write"],
            },
        )
        response.raise_for_status()
        return response.json()
