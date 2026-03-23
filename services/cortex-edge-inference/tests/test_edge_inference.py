from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
for root in (ROOT, CORE_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_edge_inference.config import EdgeInferenceConfig
from cortex_edge_inference.main import create_app, infer_edge_risk
from cortex_edge_inference.models import EdgeContext, EdgeInferenceRequest


def test_edge_risk_increases_for_missing_fingerprint_and_rare_path() -> None:
    req = EdgeInferenceRequest(
        session_id="sess-1",
        entity_id="user-1",
        trace_id="trace-1",
        context=EdgeContext(
            ip_reputation=72,
            geo_consistency=0.2,
            device_fingerprint_present=False,
            path_anomaly_score=80,
            auth_context_score=45,
            previous_session_chain_score=40,
            transport_risk=70,
            vpn_or_proxy_detected=True,
            related_anomalous_sessions=2,
            asn_risk=75,
        ),
    )
    signal = infer_edge_risk(req, EdgeInferenceConfig())
    assert signal.inferred_edge_risk >= 80
    assert signal.confidence >= 0.75
    assert any(item.code == "fingerprint_missing" for item in signal.evidence)
    assert signal.route_hint == "sentinel_immediate_attention"


def test_disabled_service_fails_closed() -> None:
    app = create_app(
        EdgeInferenceConfig(
            enabled=False,
            audit_required=False,
            trust_forward_enabled=False,
            trust_forward_required=False,
        )
    )
    client = TestClient(app)
    response = client.post(
        "/v1/edge/infer",
        json={
            "session_id": "sess-2",
            "entity_id": "user-2",
            "trace_id": "trace-2",
            "context": {},
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "edge_inference_disabled"


def test_metrics_endpoint_exposes_prometheus_format() -> None:
    app = create_app(
        EdgeInferenceConfig(
            audit_required=False,
            trust_forward_enabled=False,
            trust_forward_required=False,
        )
    )
    client = TestClient(app)
    client.post(
        "/v1/edge/infer",
        json={
            "session_id": "sess-3",
            "entity_id": "user-3",
            "trace_id": "trace-3",
            "context": {"device_fingerprint_present": False, "path_anomaly_score": 50},
        },
    )
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "cortex_edge_inference_requests_total 1" in metrics.text


def test_ready_without_required_dependencies_returns_200() -> None:
    app = create_app(
        EdgeInferenceConfig(
            audit_required=False,
            trust_forward_enabled=False,
            trust_forward_required=False,
        )
    )
    client = TestClient(app)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
