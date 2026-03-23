from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_insider_decay.engine import InsiderDecayStore
from cortex_insider_decay.main import create_app
from cortex_insider_decay.models import InsiderEvaluationRequest, InsiderEvent


def test_cumulative_decay_increases_with_repeated_subtle_deviations() -> None:
    store = InsiderDecayStore()
    for hour in [22, 23, 5]:
        store.ingest(
            InsiderEvent(
                identity_id="user-1",
                role="finance",
                expected_role="finance",
                justification_present=False,
                data_criticality="critical",
                hour_utc=hour,
                organization_context="off_process",
            )
        )
    signal = store.evaluate(
        InsiderEvaluationRequest(
            identity_id="user-1",
            trace_id="trace-insider-1",
            events=[
                InsiderEvent(
                    identity_id="user-1",
                    role="finance",
                    expected_role="finance",
                    justification_present=False,
                    data_criticality="critical",
                    hour_utc=23,
                    organization_context="off_process",
                )
            ],
        )
    )
    assert signal.cumulative_trust_decay >= 60
    assert any("repeated subtle deviations" in item or "business context" in item for item in signal.evidence)


def test_insider_service_exposes_endpoints() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/startup").status_code == 200
        stored = client.post(
            "/v1/insider/events",
            json={
                "identity_id": "user-2",
                "role": "ops",
                "expected_role": "ops",
                "justification_present": False,
                "data_criticality": "high",
                "hour_utc": 23,
                "organization_context": "off_process",
                "trace_id": "trace-insider-2",
            },
        )
        assert stored.status_code == 200
        evaluated = client.post(
            "/v1/insider/evaluate",
            json={
                "identity_id": "user-2",
                "trace_id": "trace-insider-2",
                "events": [
                    {
                        "identity_id": "user-2",
                        "role": "ops",
                        "expected_role": "ops",
                        "justification_present": False,
                        "data_criticality": "critical",
                        "hour_utc": 23,
                        "organization_context": "off_process",
                    }
                ],
            },
        )
        assert evaluated.status_code == 200
        assert evaluated.json()["signal"]["signal"] == "insider_trust_decay"
