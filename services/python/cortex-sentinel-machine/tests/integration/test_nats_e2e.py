from pathlib import Path
import asyncio
import shutil
import time
import uuid

import pytest

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.runtime import SentinelRuntime
from app.service import SentinelMachineService


async def _publish_command(nats_url: str, machine_id: str) -> None:
    import nats

    nc = await nats.connect(nats_url, connect_timeout=1, allow_reconnect=False, max_reconnect_attempts=0)
    js = nc.jetstream()
    try:
        await js.publish(
            "cortex.sentinel.commands",
            (
                f'{{"type":"flush_pending","machine_id":"{machine_id}"}}'.encode("utf-8")
            ),
        )
    finally:
        await nc.drain()


@pytest.mark.integration
def test_nats_command_bus_flushes_pending_records() -> None:
    root = Path("test-artifacts") / f"nats-e2e-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    settings = RuntimeSettings(
        queue_path=root / "queue.log",
        state_dir=root / "state",
        enable_nats_bus=True,
        nats_url="nats://127.0.0.1:4223",
        nats_connect_timeout_seconds=0.5,
    )
    try:
        service = SentinelMachineService(settings, SyntheticCollector(settings))
    except Exception as exc:
        shutil.rmtree(root, ignore_errors=True)
        pytest.skip(f"nats unavailable: {exc}")
        return

    try:
        runtime = SentinelRuntime(service)
        assert runtime.register_command_subscription() is True

        service.transport.bus = None
        service.transport.emit("telemetry", {"event_id": "pending-1", "trace_id": "trace-1"})
        assert service.queue.depth() == 1

        service.transport.bus = service.nats_bus
        asyncio.run(_publish_command(settings.nats_url, settings.machine_id))

        deadline = time.time() + 5
        while time.time() < deadline and service.queue.depth() != 0:
            time.sleep(0.1)

        assert service.queue.depth() == 0
    finally:
        service.close()
        shutil.rmtree(root, ignore_errors=True)
