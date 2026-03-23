import hashlib
import hmac
import json
from pathlib import Path

from fastapi.testclient import TestClient

from cortex_orchestrator.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_model_promote_accepts_signed_candidate() -> None:
    client = TestClient(app)
    body = {
        "model_id": "shadow-1",
        "parent_model_id": "champion-1",
        "tenant_scope": "tenant-1",
        "machine_scope": "machine-1",
        "class_scope": "workstation",
        "training_window": "short=64,long=512",
        "feature_schema_hash": "schema-1",
        "evaluation_report": {
            "shadow_vs_champion_delta": 0.2,
            "baseline_stability_score": 0.9,
        },
        "rollback_pointer": "champion-1",
        "parameters": {},
    }
    manifest_body = {
        "model_id": body["model_id"],
        "parent_model_id": body["parent_model_id"],
        "tenant_scope": body["tenant_scope"],
        "machine_scope": body["machine_scope"],
        "training_window": body["training_window"],
        "feature_schema_hash": body["feature_schema_hash"],
    }
    payload = json.dumps(manifest_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(b"sentinel-machine-dev-key-32-bytes!!", payload, hashlib.sha256).hexdigest()
    body["signed_manifest"] = {
        "algorithm": "hmac-sha256",
        "body": manifest_body,
        "signature": signature,
        "signer": "spiffe://cortex/sentinel-machine/host1",
    }

    response = client.post("/v1/model/promote", json=body, headers={"x-cortex-internal-token": "cortex-internal-dev-token"})

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert response.json()["mode"] == "promote"


def test_model_promote_rejects_invalid_manifest() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/model/promote",
        json={
            "model_id": "shadow-1",
            "tenant_scope": "tenant-1",
            "machine_scope": "machine-1",
            "class_scope": "workstation",
            "training_window": "short=64,long=512",
            "feature_schema_hash": "schema-1",
            "signed_manifest": {"algorithm": "hmac-sha256", "body": {}, "signature": "bad"},
        },
        headers={"x-cortex-internal-token": "cortex-internal-dev-token"},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is False


def test_model_promote_persists_audit_log(monkeypatch) -> None:
    client = TestClient(app)
    root = Path("test-artifacts")
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "orchestrator-model-audit.jsonl"
    if log_path.exists():
        log_path.unlink()
    monkeypatch.setenv("CORTEX_ORCHESTRATOR_MODEL_AUDIT_LOG", str(log_path))
    body = {
        "model_id": "shadow-2",
        "parent_model_id": "champion-1",
        "tenant_scope": "tenant-1",
        "machine_scope": "machine-1",
        "class_scope": "workstation",
        "training_window": "short=64,long=512",
        "feature_schema_hash": "schema-1",
        "evaluation_report": {
            "shadow_vs_champion_delta": 0.2,
            "baseline_stability_score": 0.9,
        },
        "rollback_pointer": "champion-1",
        "parameters": {},
    }
    manifest_body = {
        "model_id": body["model_id"],
        "parent_model_id": body["parent_model_id"],
        "tenant_scope": body["tenant_scope"],
        "machine_scope": body["machine_scope"],
        "training_window": body["training_window"],
        "feature_schema_hash": body["feature_schema_hash"],
    }
    payload = json.dumps(manifest_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(b"sentinel-machine-dev-key-32-bytes!!", payload, hashlib.sha256).hexdigest()
    body["signed_manifest"] = {
        "algorithm": "hmac-sha256",
        "body": manifest_body,
        "signature": signature,
        "signer": "spiffe://cortex/sentinel-machine/host1",
    }

    response = client.post("/v1/model/promote", json=body, headers={"x-cortex-internal-token": "cortex-internal-dev-token"})

    assert response.status_code == 200
    assert log_path.exists() is True
    assert "shadow-2" in log_path.read_text(encoding="utf-8")


def test_colab_ingest_rejects_unsigned_payload() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/training/colab/ingest",
        json={
            "source": "google_colab",
            "run_id": "run-1",
            "training_plan_id": "plan-1",
            "target_agents": ["decision"],
            "dataset_fingerprint": "fingerprint-12345678",
            "verification": {
                "status": "verified",
                "novelty_gate_applied": True,
                "offensive_content_filtered": True,
                "known_attack_filter_applied": True,
                "human_reviewed": True,
                "accepted_count": 1,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["reason"] == "invalid_colab_signature"


def test_colab_ingest_accepts_verified_payload(monkeypatch) -> None:
    client = TestClient(app)
    root = Path("test-artifacts")
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "orchestrator-colab-audit.jsonl"
    if log_path.exists():
        log_path.unlink()
    monkeypatch.setenv("CORTEX_ORCHESTRATOR_MODEL_AUDIT_LOG", str(log_path))
    monkeypatch.setenv("CORTEX_COLAB_SHARED_SECRET", "colab-secret")
    candidate = {
        "model_id": "shadow-colab-1",
        "parent_model_id": "champion-1",
        "tenant_scope": "tenant-1",
        "machine_scope": "machine-1",
        "class_scope": "workstation",
        "training_window": "short=64,long=512",
        "feature_schema_hash": "schema-1",
        "evaluation_report": {
            "shadow_vs_champion_delta": 0.2,
            "baseline_stability_score": 0.9,
        },
        "rollback_pointer": "champion-1",
        "parameters": {},
    }
    manifest_body = {
        "model_id": candidate["model_id"],
        "parent_model_id": candidate["parent_model_id"],
        "tenant_scope": candidate["tenant_scope"],
        "machine_scope": candidate["machine_scope"],
        "training_window": candidate["training_window"],
        "feature_schema_hash": candidate["feature_schema_hash"],
    }
    payload = json.dumps(manifest_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(b"sentinel-machine-dev-key-32-bytes!!", payload, hashlib.sha256).hexdigest()
    candidate["signed_manifest"] = {
        "algorithm": "hmac-sha256",
        "body": manifest_body,
        "signature": signature,
        "signer": "spiffe://cortex/sentinel-machine/host1",
    }
    body = {
        "source": "google_colab",
        "run_id": "run-2",
        "training_plan_id": "plan-2",
        "target_agents": ["decision", "ad"],
        "dataset_fingerprint": "fingerprint-abcdef123456",
        "knowledge_registry_fingerprint": "known-1234",
        "accepted_item_ids": ["evt-9", "drift-9"],
        "verification": {
            "status": "verified",
            "novelty_gate_applied": True,
            "offensive_content_filtered": True,
            "known_attack_filter_applied": True,
            "human_reviewed": True,
            "accepted_count": 2,
            "reviewer": "analyst@cortex.local",
        },
        "candidate": candidate,
        "metadata": {"source_kind": "internal-curated"},
    }
    signed = hmac.new(b"colab-secret", json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"), hashlib.sha256).hexdigest()

    response = client.post(
        "/v1/training/colab/ingest",
        json=body,
        headers={"x-cortex-colab-signature": signed},
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert response.json()["promotion"]["accepted"] is True
    assert log_path.exists() is True
    assert "colab_training_ingested" in log_path.read_text(encoding="utf-8")


def test_colab_ingest_blocks_unreviewed_candidate(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setenv("CORTEX_COLAB_SHARED_SECRET", "colab-secret")
    body = {
        "source": "google_colab",
        "run_id": "run-3",
        "training_plan_id": "plan-3",
        "target_agents": ["decision"],
        "dataset_fingerprint": "fingerprint-zxy987654321",
        "verification": {
            "status": "verified",
            "novelty_gate_applied": True,
            "offensive_content_filtered": True,
            "known_attack_filter_applied": True,
            "human_reviewed": False,
            "accepted_count": 1,
        },
        "candidate": {
            "model_id": "shadow-x",
            "tenant_scope": "tenant-1",
            "machine_scope": "machine-1",
            "class_scope": "workstation",
            "training_window": "short=64,long=512",
            "feature_schema_hash": "schema-1",
            "signed_manifest": {"algorithm": "hmac-sha256", "body": {}, "signature": "bad"},
        },
    }
    signed = hmac.new(b"colab-secret", json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8"), hashlib.sha256).hexdigest()
    response = client.post(
        "/v1/training/colab/ingest",
        json=body,
        headers={"x-cortex-colab-signature": signed},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] is False
    assert response.json()["reason"] == "candidate_requires_human_review"


def test_meta_decision_assess_returns_trusted_output(monkeypatch) -> None:
    client = TestClient(app)
    root = Path("test-artifacts")
    root.mkdir(parents=True, exist_ok=True)
    log_path = root / "orchestrator-meta-decision-audit.jsonl"
    if log_path.exists():
        log_path.unlink()
    monkeypatch.setenv("CORTEX_ORCHESTRATOR_META_DECISION_AUDIT_LOG", str(log_path))
    response = client.post(
        "/v1/meta-decision/assess",
        json={
            "event_id": "evt-1",
            "entity_id": "node-1",
            "entity_type": "machine",
            "novelty_score": 0.9,
            "graph_score": 0.8,
            "temporal_score": 0.7,
            "asset_criticality": 0.95,
            "blast_radius": 0.85,
            "crown_jewel": True,
            "signals": [
                {
                    "entity_id": "node-1",
                    "entity_type": "machine",
                    "agent_id": "decision",
                    "specialty": "response_decision",
                    "risk_signal": 0.95,
                    "priority": 0.9,
                    "runtime_trust": 0.5,
                    "uncertainty": 0.55,
                    "data_quality": 0.75,
                    "reasoning_quality": 0.8,
                },
                {
                    "entity_id": "node-1",
                    "entity_type": "machine",
                    "agent_id": "remediation",
                    "specialty": "containment_planning",
                    "risk_signal": 0.1,
                    "priority": 0.8,
                    "runtime_trust": 0.45,
                    "uncertainty": 0.6,
                    "data_quality": 0.7,
                    "reasoning_quality": 0.72,
                },
            ],
        },
        headers={"x-cortex-internal-token": "cortex-internal-dev-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["meta_decision"]["trusted_output"]["deep_analysis_triggered"] is True
    assert log_path.exists() is True


def test_decision_includes_meta_decision_payload() -> None:
    client = TestClient(app)

    class FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    captured: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict[str, object]):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse({"ok": True})

    import cortex_orchestrator.main as main_module

    main_module.httpx.AsyncClient = FakeAsyncClient
    response = client.post(
        "/v1/decision",
        json={
            "request_id": "req-1",
            "task": "quarantine",
            "payload": "suspicious activity",
            "risk_level": 5,
            "actions": ["execute_irreversible_containment"],
        },
    )
    assert response.status_code == 200
    meta_decision = captured["json"]["params"]["meta_decision"]
    assert meta_decision["trusted_output"]["deep_analysis_triggered"] is True
    assert meta_decision["trusted_output"]["selected_agents"] == ["orchestrator"]
