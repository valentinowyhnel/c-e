from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_priority_engine.engine import compute_priority
from cortex_priority_engine.main import create_app
from cortex_priority_engine.models import PriorityEvaluationRequest


def test_priority_routing_goes_deep_for_campaign_plus_criticality() -> None:
    signal = compute_priority(
        PriorityEvaluationRequest(
            entity_id="identity-1",
            anomaly_score=61,
            novelty_score=59,
            trust_score=43,
            graph_expansion=52,
            asset_criticality=85,
            campaign_likelihood=76,
            trace_id="trace-prio-1",
        )
    )
    assert signal.priority_score >= 60
    assert signal.route in {"deep_graph_reasoning", "sentinel_immediate_attention"}
    assert any("campaign likelihood" in item for item in signal.evidence)


def test_priority_service_exposes_health_metrics_and_version() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/startup").status_code == 200
        assert client.get("/version").status_code == 200
        result = client.post(
            "/v1/priority/evaluate",
            json={
                "entity_id": "identity-2",
                "anomaly_score": 45,
                "novelty_score": 38,
                "trust_score": 61,
                "graph_expansion": 28,
                "asset_criticality": 20,
                "campaign_likelihood": 14,
                "trace_id": "trace-prio-2",
            },
        )
        assert result.status_code == 200
        metrics = client.get("/metrics")
        assert "cortex_priority_engine_requests_total 1" in metrics.text
