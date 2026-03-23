from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_campaign_memory.main import create_app
from cortex_campaign_memory.store import CampaignMemoryStore
from cortex_campaign_memory.models import CampaignEventFingerprint


def test_progressive_deviation_and_likelihood_increase_for_low_and_slow() -> None:
    store = CampaignMemoryStore()
    now = time.time()
    for offset_days, weak_signal in [(28, 24), (18, 28), (9, 31), (2, 34)]:
        store.store_event_fingerprint(
            CampaignEventFingerprint(
                identity_id="admin-1",
                path_id="rare-vpn",
                resource_family="secrets",
                weak_signal_score=weak_signal,
                novelty_score=62,
                anomaly_score=51,
                timestamp=now - offset_days * 24 * 3600,
            )
        )

    signal = store.campaign_likelihood_score("admin-1", "rare-vpn", "secrets", trace_id="trace-camp-1")
    assert signal.progressive_deviation_score >= 50
    assert signal.campaign_likelihood_score >= 70
    assert any("low-and-slow" in item or "persistent" in item for item in signal.evidence)


def test_service_stores_and_evaluates_campaign_signal() -> None:
    app = create_app()
    client = TestClient(app)
    stored = client.post(
        "/v1/campaign/events",
        json={
            "identity_id": "user-1",
            "path_id": "path-1",
            "resource_family": "finance",
            "weak_signal_score": 35,
            "novelty_score": 58,
            "anomaly_score": 42,
            "trace_id": "trace-camp-2",
        },
    )
    assert stored.status_code == 200

    evaluated = client.post(
        "/v1/campaign/evaluate",
        json={
            "identity_id": "user-1",
            "path_id": "path-1",
            "resource_family": "finance",
            "trace_id": "trace-camp-2",
        },
    )
    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["signal"]["signal"] == "campaign_likelihood"
    assert body["signal"]["trace_id"] == "trace-camp-2"
    assert len(body["signal"]["windows"]) == 4
