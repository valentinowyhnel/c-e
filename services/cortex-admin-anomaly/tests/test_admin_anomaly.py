from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_admin_anomaly.engine import AdminBehaviorStore
from cortex_admin_anomaly.main import create_app
from cortex_admin_anomaly.models import AdminActionEvent


def test_admin_session_escalation_detects_causal_break() -> None:
    store = AdminBehaviorStore()
    for action in ["read_ticket", "read_ticket", "unlock_user"]:
        store.ingest(AdminActionEvent(admin_id="admin-1", action=action, resource_family="it-ops"))

    signal = store.admin_session_escalation_detector(
        "admin-1",
        [
            AdminActionEvent(admin_id="admin-1", action="unlock_user", resource_family="it-ops"),
            AdminActionEvent(admin_id="admin-1", action="dump_secrets", resource_family="crown-jewel-secrets", privilege_level="domain_admin"),
        ],
        trace_id="trace-admin-1",
        correlation_id="corr-admin-1",
    )
    assert signal.admin_session_escalation_score >= 70
    assert any("causal chain" in item or "resource family unusual" in item for item in signal.evidence)


def test_admin_service_health_and_evaluate() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/startup").status_code == 200
        history = client.post(
            "/v1/admin/history",
            json={"admin_id": "admin-2", "action": "read_ticket", "resource_family": "it-ops", "trace_id": "trace-admin-2"},
        )
        assert history.status_code == 200
        result = client.post(
            "/v1/admin/evaluate",
            json={
                "admin_id": "admin-2",
                "trace_id": "trace-admin-2",
                "actions": [
                    {"admin_id": "admin-2", "action": "rotate_breakglass", "resource_family": "crown-jewel-secrets", "privilege_level": "domain_admin"}
                ],
            },
        )
        assert result.status_code == 200
        assert result.json()["signal"]["signal"] == "admin_compromise_suspected"
