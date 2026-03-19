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
