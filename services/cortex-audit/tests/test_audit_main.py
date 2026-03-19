from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from cortex_audit.main import app, events


client = TestClient(app)


def setup_function() -> None:
    events.clear()
    os.environ.pop("CORTEX_INTERNAL_API_TOKEN", None)


def create_event(principal_id: str = "cortex-obs-agent") -> dict:
    response = client.post(
        "/v1/events",
        json={
            "principal_id": principal_id,
            "principal_type": "ai_agent",
            "event_type": "obs.autonomous_action",
            "action": "write",
            "decision": "allow",
            "reason": "restart pod",
            "risk_level": 2,
            "metadata": {"service": "cortex-auth"},
            "correlation_id": "corr-123",
            "action_class": "prepare_only",
            "execution_mode": "prepare",
            "capability_maturity": "beta",
            "degraded_mode": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_write_event_records_signature_and_id() -> None:
    response = create_event()
    assert response["status"] == "recorded"
    assert response["event_id"]
    assert response["signature"]


def test_list_events_returns_latest_first() -> None:
    create_event("agent-1")
    create_event("agent-2")
    response = client.get("/v1/events")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["principal_id"] == "agent-2"


def test_list_events_filters_by_principal() -> None:
    create_event("agent-1")
    create_event("agent-2")
    response = client.get("/v1/events?principal_id=agent-1")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["principal_id"] == "agent-1"


def test_get_event_by_id() -> None:
    created = create_event()
    response = client.get(f"/v1/events/{created['event_id']}")
    assert response.status_code == 200
    assert response.json()["event_id"] == created["event_id"]


def test_event_contains_maturity_and_degraded_snapshot() -> None:
    created = create_event("agent-3")
    response = client.get(f"/v1/events/{created['event_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["correlation_id"] == "corr-123"
    assert body["action_class"] == "prepare_only"
    assert body["execution_mode"] == "prepare"
    assert body["capability_maturity"] == "beta"
    assert body["degraded_mode"] is True


def test_internal_token_required_when_configured() -> None:
    os.environ["CORTEX_INTERNAL_API_TOKEN"] = "secret-token"

    response = client.get("/v1/events")
    assert response.status_code == 403

    response = client.get(
        "/v1/events",
        headers={"x-cortex-internal-token": "secret-token"},
    )
    assert response.status_code == 200
