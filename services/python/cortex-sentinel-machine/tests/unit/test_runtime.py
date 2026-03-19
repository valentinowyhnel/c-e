from pathlib import Path
import json
import shutil
import uuid

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.runtime import SentinelRuntime
from app.service import SentinelMachineService


class FakeBus:
    def __init__(self) -> None:
        self.subscriptions: list[tuple[str, object, str]] = []
        self.stopped = False

    def subscribe(self, subject: str, cb, durable: str) -> bool:
        self.subscriptions.append((subject, cb, durable))
        return True

    def stop(self) -> None:
        self.stopped = True


def _service() -> SentinelMachineService:
    root = Path("test-artifacts") / f"runtime-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    settings = RuntimeSettings(queue_path=root / "queue.log", state_dir=root / "state", enable_nats_bus=False)
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    service._test_root = root  # type: ignore[attr-defined]
    return service


def _cleanup(service: SentinelMachineService) -> None:
    root = getattr(service, "_test_root", None)
    if root is not None:
        shutil.rmtree(root, ignore_errors=True)


def test_runtime_flush_pending_command() -> None:
    service = _service()
    try:
        service.transport.emit("telemetry", {"event_id": "e1"})
        runtime = SentinelRuntime(service)
        response = runtime.handle_command({"type": "flush_pending"})
        assert response["accepted"] is True
    finally:
        _cleanup(service)


def test_runtime_disable_nats_bus_command() -> None:
    service = _service()
    try:
        fake_bus = FakeBus()
        service.nats_bus = fake_bus  # type: ignore[assignment]
        service.transport.bus = fake_bus
        runtime = SentinelRuntime(service)
        response = runtime.handle_command({"type": "disable_nats_bus"})
        assert response["accepted"] is True
        assert fake_bus.stopped is True
        assert service.transport.bus is None
    finally:
        _cleanup(service)


def test_runtime_registers_command_subscription() -> None:
    service = _service()
    try:
        fake_bus = FakeBus()
        service.nats_bus = fake_bus  # type: ignore[assignment]
        runtime = SentinelRuntime(service)
        assert runtime.register_command_subscription() is True
        assert fake_bus.subscriptions[0][0] == "cortex.sentinel.commands"
    finally:
        _cleanup(service)
