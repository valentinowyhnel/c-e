from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from app.service import SentinelMachineService


class SecureObservabilityServer:
    def __init__(self, service: SentinelMachineService, token: str) -> None:
        self.service = service
        self.token = token
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self, host: str, port: int) -> None:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.headers.get("Authorization") != f"Bearer {parent.token}":
                    self.send_response(401)
                    self.end_headers()
                    return
                if self.path == "/health":
                    payload = json.dumps(asdict(parent.service.health())).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if self.path == "/metrics":
                    lines = [f"{key} {value}" for key, value in sorted(parent.service.metrics.snapshot().items())]
                    payload = ("\n".join(lines) + "\n").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
