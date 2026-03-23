from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOTS = [
    ROOT / "services" / "cortex-campaign-memory",
    ROOT / "services" / "cortex-priority-engine",
]
for root in SERVICE_ROOTS:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_campaign_memory.main import create_app as create_campaign_app  # noqa: E402
from cortex_priority_engine.main import create_app as create_priority_app  # noqa: E402


def test_campaign_memory_signal_drives_priority_route() -> None:
    campaign_app = create_campaign_app()
    priority_app = create_priority_app()

    with TestClient(campaign_app) as campaign_client, TestClient(priority_app) as priority_client:
        now = time.time()
        for offset_days, weak_signal in [(26, 26), (18, 29), (10, 31), (4, 33)]:
            stored = campaign_client.post(
                "/v1/campaign/events",
                json={
                    "identity_id": "identity-int-1",
                    "path_id": "path-int-rare",
                    "resource_family": "finance-ledger",
                    "weak_signal_score": weak_signal,
                    "novelty_score": 61,
                    "anomaly_score": 48,
                    "timestamp": now - offset_days * 24 * 3600,
                    "trace_id": "trace-int-1",
                },
            )
            assert stored.status_code == 200

        campaign_response = campaign_client.post(
            "/v1/campaign/evaluate",
            json={
                "identity_id": "identity-int-1",
                "path_id": "path-int-rare",
                "resource_family": "finance-ledger",
                "trace_id": "trace-int-1",
            },
        )
        assert campaign_response.status_code == 200
        likelihood = campaign_response.json()["signal"]["campaign_likelihood_score"]
        assert likelihood >= 65

        priority_response = priority_client.post(
            "/v1/priority/evaluate",
            json={
                "entity_id": "identity-int-1",
                "anomaly_score": 54,
                "novelty_score": 58,
                "trust_score": 46,
                "graph_expansion": 49,
                "asset_criticality": 72,
                "campaign_likelihood": likelihood,
                "trace_id": "trace-int-1",
            },
        )
        assert priority_response.status_code == 200
        route = priority_response.json()["signal"]["route"]
        assert route in {"hybrid_analysis", "deep_graph_reasoning", "sentinel_immediate_attention"}
