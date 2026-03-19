from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_obs_agent.main import app, feed_events, loop_status, service_health


client = TestClient(app)


def setup_function() -> None:
    os.environ.pop("CORTEX_INTERNAL_API_TOKEN", None)
    feed_events.clear()
    loop_status.clear()
    service_health.clear()


def test_healthz_remains_open() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200


def test_internal_token_required_when_configured() -> None:
    os.environ["CORTEX_INTERNAL_API_TOKEN"] = "secret-token"

    response = client.get("/v1/feed")
    assert response.status_code == 403

    response = client.get(
        "/v1/feed",
        headers={"x-cortex-internal-token": "secret-token"},
    )
    assert response.status_code == 200
