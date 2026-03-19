from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import json
import shutil
import time
import uuid

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.service import SentinelMachineService


class _Recorder:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object], dict[str, str]]] = []


def _start_server(host: str, port: int, recorder: _Recorder) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            recorder.requests.append((self.path, payload, {key.lower(): value for key, value in self.headers.items()}))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if self.path.endswith("/v1/sentinel/events"):
                self.wfile.write(json.dumps({"accepted": True, "event_id": payload["event_id"]}).encode("utf-8"))
            elif self.path.endswith("/trust/evaluate/v2"):
                self.wfile.write(json.dumps({"trust_score": 71.0, "decision": "monitor"}).encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"promotion": "shadow"}).encode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_sync_to_cortex_control_plane() -> None:
    root = Path("test-artifacts") / f"sync-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    ingest = _Recorder()
    trust = _Recorder()
    model = _Recorder()
    ingest_server = _start_server("127.0.0.1", 28081, ingest)
    trust_server = _start_server("127.0.0.1", 28082, trust)
    model_server = _start_server("127.0.0.1", 28083, model)
    try:
        settings = RuntimeSettings(
            queue_path=root / "queue.log",
            state_dir=root / "state",
            min_training_support=1,
            promotion_patience=1,
            cortex_ingest_url="http://127.0.0.1:28081",
            cortex_trust_url="http://127.0.0.1:28082",
            cortex_model_url="http://127.0.0.1:28083",
            cortex_internal_token="token-123",
        )
        service = SentinelMachineService(settings, SyntheticCollector(settings))
        outcome = service.process_once()[0]
        response = service.sync_outcome(outcome)
        time.sleep(0.2)
        assert response["ingest"]["accepted"] is True
        assert response["trust"]["decision"] == "monitor"
        assert response["model"]["promotion"] == "shadow"
        assert ingest.requests[0][0] == "/v1/sentinel/events"
        assert trust.requests[0][0] == "/trust/evaluate/v2"
        assert model.requests[0][0] == "/v1/model/promote"
        assert trust.requests[0][2]["x-cortex-internal-token"] == "token-123"
        assert model.requests[0][2]["x-cortex-internal-token"] == "token-123"
    finally:
        ingest_server.shutdown()
        trust_server.shutdown()
        model_server.shutdown()
        ingest_server.server_close()
        trust_server.server_close()
        model_server.server_close()
        shutil.rmtree(root, ignore_errors=True)
