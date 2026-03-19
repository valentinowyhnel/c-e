from __future__ import annotations

import asyncio
import json
import os
import signal

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
        loop.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())
