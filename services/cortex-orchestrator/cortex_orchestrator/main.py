import os
import json
import hmac
import hashlib
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Header, Request
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


class ColabVerificationRequest(BaseModel):
    status: Literal["verified", "rejected"] = "verified"
    novelty_gate_applied: bool = True
    offensive_content_filtered: bool = True
    known_attack_filter_applied: bool = True
    human_reviewed: bool = False
    accepted_count: int = Field(default=0, ge=0)
    skipped_known_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    reviewer: str = ""
    notes: str = ""


class ColabTrainingSyncRequest(BaseModel):
    source: Literal["google_colab"] = "google_colab"
    run_id: str
    training_plan_id: str
    target_agents: list[str] = Field(default_factory=list)
    dataset_fingerprint: str = Field(min_length=8)
    knowledge_registry_fingerprint: str = ""
    accepted_item_ids: list[str] = Field(default_factory=list)
    verification: ColabVerificationRequest
    candidate: ModelCandidateRequest | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


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


def _colab_signing_secret() -> bytes:
    return os.getenv("CORTEX_COLAB_SHARED_SECRET", "cortex-colab-dev-secret").encode("utf-8")


def _canonical_payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_colab_signature(payload: dict[str, object], signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(_colab_signing_secret(), _canonical_payload_bytes(payload), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _evaluate_candidate(req: ModelCandidateRequest) -> dict[str, object]:
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
    return {
        "accepted": True,
        "model_id": req.model_id,
        "mode": mode,
        "promotion": promotion,
        "rollback_pointer": req.rollback_pointer,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cortex-orchestrator"}


@app.post("/v1/model/promote")
async def promote_model(req: ModelCandidateRequest, x_cortex_internal_token: str | None = Header(default=None)) -> dict[str, object]:
    if not _verify_internal_token(x_cortex_internal_token):
        return {"accepted": False, "reason": "internal_api_auth_required"}
    response = _evaluate_candidate(req)
    _append_model_audit(
        {
            "event_type": "model_candidate_received",
            "model_id": req.model_id,
            "tenant_scope": req.tenant_scope,
            "machine_scope": req.machine_scope,
            "mode": response.get("mode", "rejected"),
            "promotion": response.get("promotion", False),
            "rollback_pointer": req.rollback_pointer,
        }
    )
    return response


@app.post("/v1/training/colab/ingest")
async def ingest_colab_training_result(
    req: ColabTrainingSyncRequest,
    x_cortex_colab_signature: str | None = Header(default=None),
) -> dict[str, object]:
    if not _verify_colab_signature(
        req.model_dump(exclude_none=True, exclude_unset=True),
        x_cortex_colab_signature,
    ):
        return {"accepted": False, "reason": "invalid_colab_signature"}

    verification = req.verification
    if verification.status != "verified":
        return {"accepted": False, "reason": "verification_not_passed"}
    if not verification.novelty_gate_applied:
        return {"accepted": False, "reason": "novelty_gate_required"}
    if not verification.known_attack_filter_applied:
        return {"accepted": False, "reason": "known_attack_filter_required"}
    if not verification.offensive_content_filtered:
        return {"accepted": False, "reason": "offensive_filter_required"}
    if req.candidate and not verification.human_reviewed:
        return {"accepted": False, "reason": "candidate_requires_human_review"}

    promotion_result: dict[str, object] | None = None
    if req.candidate:
        promotion_result = _evaluate_candidate(req.candidate)

    response = {
        "accepted": True,
        "source": req.source,
        "run_id": req.run_id,
        "training_plan_id": req.training_plan_id,
        "target_agents": req.target_agents,
        "accepted_item_ids": req.accepted_item_ids,
        "promotion": promotion_result,
    }
    _append_model_audit(
        {
            "event_type": "colab_training_ingested",
            "run_id": req.run_id,
            "training_plan_id": req.training_plan_id,
            "target_agents": req.target_agents,
            "dataset_fingerprint": req.dataset_fingerprint,
            "knowledge_registry_fingerprint": req.knowledge_registry_fingerprint,
            "accepted_item_ids": req.accepted_item_ids,
            "verification": req.verification.model_dump(),
            "promotion": promotion_result,
            "metadata": req.metadata,
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
