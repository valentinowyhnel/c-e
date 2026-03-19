from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from cortex_approval.main import app, requests


client = TestClient(app)


def setup_function() -> None:
    requests.clear()
    os.environ.pop("CORTEX_INTERNAL_API_TOKEN", None)


def create_request(risk_level: int = 4) -> dict:
    response = client.post(
        "/v1/approvals",
        json={
            "plan_id": "plan-1",
            "requestor_id": "cortex-obs-agent",
            "actions": [
                {
                    "taskId": "task-1",
                    "intent": "restart_pod cortex-auth",
                    "riskLevel": risk_level,
                    "dryRunRequired": True,
                }
            ],
            "reasoning": "Need approval",
            "risk_level": risk_level,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_create_and_get_approval() -> None:
    payload = create_request()

    fetched = client.get(f"/v1/approvals/{payload['request_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["request_id"] == payload["request_id"]
    assert fetched.json()["status"] == "pending"


def test_list_filters_pending_only_by_default() -> None:
    pending = create_request()
    approved = create_request()
    client.post(f"/v1/approvals/{approved['request_id']}/approve", json={"comment": "ok"})

    response = client.get("/v1/approvals")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["request_id"] == pending["request_id"]


def test_list_all_includes_resolved() -> None:
    approved = create_request()
    client.post(f"/v1/approvals/{approved['request_id']}/approve", json={"comment": "ok"})

    response = client.get("/v1/approvals?status=all")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "approved"


def test_risk_five_requires_two_approvals() -> None:
    payload = create_request(risk_level=5)
    first = client.post(f"/v1/approvals/{payload['request_id']}/approve", json={"comment": "first"})
    assert first.status_code == 200
    assert first.json()["status"] == "pending"
    assert first.json()["approvals_received"] == 1

    second = client.post(f"/v1/approvals/{payload['request_id']}/approve", json={"comment": "second"})
    assert second.status_code == 200
    assert second.json()["status"] == "approved"


def test_reject_moves_to_rejected() -> None:
    payload = create_request()
    response = client.post(
        f"/v1/approvals/{payload['request_id']}/reject",
        json={"reason": "not safe"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_invalid_low_risk_request_is_rejected() -> None:
    response = client.post(
        "/v1/approvals",
        json={
            "plan_id": "plan-1",
            "requestor_id": "cortex-obs-agent",
            "actions": [
                {
                    "taskId": "task-1",
                    "intent": "restart_pod cortex-auth",
                    "riskLevel": 2,
                    "dryRunRequired": False,
                }
            ],
            "reasoning": "Need approval",
            "risk_level": 2,
        },
    )
    assert response.status_code == 422


def test_unknown_request_returns_404() -> None:
    response = client.get("/v1/approvals/not-found")
    assert response.status_code == 404


def test_internal_token_required_when_configured() -> None:
    os.environ["CORTEX_INTERNAL_API_TOKEN"] = "secret-token"
    response = client.get("/v1/approvals")
    assert response.status_code == 403

    response = client.get(
        "/v1/approvals",
        headers={"x-cortex-internal-token": "secret-token"},
    )
    assert response.status_code == 200
