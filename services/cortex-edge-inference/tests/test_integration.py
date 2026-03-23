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
from cortex_edge_inference.main import create_app


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("unexpected_http_error")


def test_edge_inference_forwards_to_trust_and_audits(monkeypatch) -> None:
    seen: list[tuple[str, dict[str, object], dict[str, str]]] = []

    async def fake_post_json(url: str, payload: dict[str, object], headers: dict[str, str], timeout_seconds: float):
        del timeout_seconds
        seen.append((url, payload, headers))
        if url.endswith("/trust/evaluate/v2"):
            return _FakeResponse(
                {
                    "entity_id": payload["entity_id"],
                    "entity_type": payload["entity_type"],
                    "trust_score": 41,
                    "threat_level": "high",
                    "response_eligibility": "approval_gated",
                    "decision": "deny",
                    "retained_evidence_count": 1,
                    "degraded": False,
                    "rationale": ["edge risk accepted"],
                }
            )
        return _FakeResponse({"status": "recorded"})

    monkeypatch.setattr("cortex_edge_inference.main._post_json", fake_post_json)
    app = create_app(EdgeInferenceConfig())
    client = TestClient(app)

    response = client.post(
        "/v1/edge/infer",
        json={
            "session_id": "sess-10",
            "entity_id": "identity-10",
            "entity_type": "identity",
            "trace_id": "trace-10",
            "correlation_id": "corr-10",
            "blast_radius": 5,
            "crown_jewels_exposed": True,
            "context": {
                "ip_reputation": 80,
                "geo_consistency": 0.3,
                "device_fingerprint_present": False,
                "path_anomaly_score": 72,
                "transport_risk": 60,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["signal"] == "edge_risk_inferred"
    assert body["trust_response"]["trust_score"] == 41
    assert len(seen) == 2
    assert seen[0][0].endswith("/v1/events")
    assert seen[1][0].endswith("/trust/evaluate/v2")
    assert seen[1][1]["evidences"][0]["source"] == "edge_inference"


def test_audit_failure_blocks_when_required(monkeypatch) -> None:
    async def fake_post_json(url: str, payload: dict[str, object], headers: dict[str, str], timeout_seconds: float):
        del url, payload, headers, timeout_seconds
        raise __import__("httpx").HTTPError("audit down")

    monkeypatch.setattr("cortex_edge_inference.main._post_json", fake_post_json)
    app = create_app(EdgeInferenceConfig())
    client = TestClient(app)

    response = client.post(
        "/v1/edge/infer",
        json={
            "session_id": "sess-11",
            "entity_id": "identity-11",
            "trace_id": "trace-11",
            "context": {"device_fingerprint_present": False},
        },
    )
    assert response.status_code == 503
    assert "audit_unavailable" in response.json()["detail"]
