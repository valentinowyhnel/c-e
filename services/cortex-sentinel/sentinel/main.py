from __future__ import annotations

import asyncio
import json
import os
import signal
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import nats
import structlog

from .engine import CortexSentinelEngine

log = structlog.get_logger()
JETSTREAM_SUBJECTS = [
    "cortex.obs.stream",
    "cortex.trust.updates",
    "cortex.security.events",
    "cortex.obs.sot.issued",
    "cortex.sentinel.commands",
    "cortex.agents.tasks.remediation",
]

HIGH_RISK_ACTIONS = {
    "execute_quarantine",
    "execute_irreversible_containment",
    "trigger_apoptosis",
    "rotate_secret",
}


def evaluate_plan_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Compatibility policy for callers still using HTTP sentinel validation."""
    risk_level = int(payload.get("risk_level", 1))
    actions = {str(action) for action in payload.get("actions", [])}
    destructive = bool(actions & HIGH_RISK_ACTIONS)
    approval_required = risk_level >= 4 or destructive
    accepted = risk_level < 5 and not destructive
    return {
        "accepted": accepted,
        "decision": "allow" if accepted else "prepare_only",
        "approval_required": approval_required,
        "forensic_required": destructive,
        "reason": "high_risk_requires_prepare_only" if not accepted else "risk_within_local_guardrails",
    }


class _CompatibilityHandler(BaseHTTPRequestHandler):
    server_version = "CortexSentinel/2"
    readiness_probe = {"status": "ok", "service": "cortex-sentinel", "mode": "daemonset_v2"}

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        log.info("sentinel.http", message=format % args)

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/health", "/healthz", "/readyz"}:
            self._write_json(HTTPStatus.OK, dict(self.readiness_probe))
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"detail": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/validate-plan":
            self._write_json(HTTPStatus.NOT_FOUND, {"detail": "not_found"})
            return
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"detail": "invalid_json"})
            return
        self._write_json(HTTPStatus.OK, evaluate_plan_request(payload))


def _start_compatibility_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), _CompatibilityHandler)
    thread = threading.Thread(target=server.serve_forever, name="sentinel-http", daemon=True)
    thread.start()
    return server


async def _ensure_stream(js) -> None:
    try:
        await js.stream_info("CORTEX_EVENTS")
    except Exception:
        try:
            await js.add_stream(name="CORTEX_EVENTS", subjects=JETSTREAM_SUBJECTS)
        except Exception as exc:
            log.warning("sentinel.stream.ensure_failed", error=str(exc)[:200])


async def _subscribe(nc, js, subject: str, cb, durable: str) -> None:
    try:
        await js.subscribe(subject, cb=cb, durable=durable)
    except Exception as exc:
        log.warning("sentinel.subscribe.jetstream_failed", subject=subject, error=str(exc)[:200])
        await nc.subscribe(subject, cb=cb)


async def main() -> None:
    entity_id = os.getenv("ENTITY_ID", os.uname().nodename)
    entity_type = os.getenv("ENTITY_TYPE", "machine")
    nats_url = os.getenv("NATS_URL", "nats://cortex-nats:4222")
    log.info("sentinel.starting", entity=entity_id)
    compatibility_server = _start_compatibility_server()
    nc = await nats.connect(nats_url)
    js = nc.jetstream()
    await _ensure_stream(js)
    engine = CortexSentinelEngine(
        entity_id=entity_id,
        entity_type=entity_type,
        nats_client=nc,
        trust_engine_url=os.getenv("TRUST_ENGINE_URL", "http://cortex-trust-engine:8080"),
    )

    async def on_command(msg) -> None:
        try:
            cmd = json.loads(msg.data)
            if cmd.get("entity_id") not in (entity_id, "*"):
                if hasattr(msg, "ack"):
                    await msg.ack()
                return
            await engine.handle_command(cmd)
            if hasattr(msg, "ack"):
                await msg.ack()
        except Exception as exc:
            log.error("command.error", error=str(exc))
            if hasattr(msg, "nak"):
                await msg.nak()

    await _subscribe(nc, js, "cortex.sentinel.commands", on_command, f"sentinel-{entity_id}")
    loop = asyncio.get_running_loop()

    def _stop(*_: object) -> None:
        log.info("sentinel.stopping")
        engine._running = False
        compatibility_server.shutdown()
        compatibility_server.server_close()
        loop.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
