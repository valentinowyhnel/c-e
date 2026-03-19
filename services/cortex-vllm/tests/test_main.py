from fastapi.testclient import TestClient

from cortex_vllm.main import app


def test_route_simple_task() -> None:
    client = TestClient(app)
    response = client.post("/v1/route", json={"task": "classify_intent", "payload": "hello"})
    assert response.status_code == 200
    assert response.json()["target"] == "local"
