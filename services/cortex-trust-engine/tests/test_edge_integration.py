from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
for root in (ROOT, CORE_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_trust_engine.main import app, profiles  # noqa: E402


client = TestClient(app)


def setup_function() -> None:
    profiles.clear()
    os.environ.pop("EDGE_INFERENCE_ENABLED", None)


def test_edge_inference_evidence_is_accepted_by_trust_engine() -> None:
    response = client.post(
        "/trust/evaluate/v2",
        json={
            "entity_id": "identity-1",
            "entity_type": "identity",
            "criticality": "critical",
            "evidences": [
                {
                    "entity_id": "identity-1",
                    "source": "edge_inference",
                    "signal_type": "edge_risk_inferred",
                    "severity": 0.82,
                    "confidence": 0.8,
                    "timestamp": time.time(),
                    "ttl": 900,
                    "metadata": {"trace_id": "trace-edge-1", "inferred": True},
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trust_score"] < 85
    assert any("edge_risk_signal" in item for item in body["rationale"])


def test_health_and_metrics_endpoints_exist() -> None:
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get("/health/startup").status_code == 200
    assert client.get("/version").status_code == 200
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "cortex_trust_engine_profiles" in metrics.text


def test_edge_inference_signal_can_be_disabled() -> None:
    os.environ["EDGE_INFERENCE_ENABLED"] = "false"
    response = client.post(
        "/trust/evaluate/v2",
        json={
            "entity_id": "identity-2",
            "entity_type": "identity",
            "evidences": [
                {
                    "entity_id": "identity-2",
                    "source": "edge_inference",
                    "signal_type": "edge_risk_inferred",
                    "severity": 0.9,
                    "confidence": 0.9,
                    "timestamp": time.time(),
                    "ttl": 900,
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["trust_score"] == 85.0
