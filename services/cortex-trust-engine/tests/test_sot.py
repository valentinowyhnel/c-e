from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
for root in (ROOT, CORE_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_trust_engine.main import app, sot_records  # noqa: E402


client = TestClient(app)


def setup_function() -> None:
    sot_records.clear()


def test_sot_issue_expire_revoke_and_impact() -> None:
    issued = client.post(
        "/trust/sot/issue",
        json={
            "entity_id": "machine-1",
            "entity_type": "machine",
            "reasons": ["cred_dump", "tamper"],
            "ttl_seconds": 60,
        },
    )
    assert issued.status_code == 200
    token_id = issued.json()["token_id"]

    impact = client.post(f"/trust/sot/{token_id}/impact")
    assert impact.status_code == 200
    assert impact.json()["active"] is True
    assert impact.json()["escalation_ready"] is True

    expired = client.post(f"/trust/sot/{token_id}/expire")
    assert expired.status_code == 200
    assert expired.json()["token_id"] == token_id

    revoked = client.post(f"/trust/sot/{token_id}/revoke", json={"reason": "operator_ack"})
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None

    fetched = client.get(f"/trust/sot/{token_id}")
    assert fetched.status_code == 200
    assert fetched.json()["token_id"] == token_id
