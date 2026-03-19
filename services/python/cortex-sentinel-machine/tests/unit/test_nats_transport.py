from pathlib import Path
import shutil
import uuid

from app.transport.client import TransportClient
from app.transport.queue import EncryptedWALQueue


class FakeBus:
    def __init__(self, succeed: bool = True) -> None:
        self.succeed = succeed
        self.messages: list[tuple[str, bytes]] = []

    def publish(self, subject: str, payload: bytes) -> bool:
        if not self.succeed:
            return False
        self.messages.append((subject, payload))
        return True


def test_transport_flushes_to_bus_when_available() -> None:
    root = Path("test-artifacts") / f"nats-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        queue = EncryptedWALQueue(root / "queue.log", "queue-key-123456789012345678901234")
        bus = FakeBus()
        client = TransportClient(queue, bus)
        client.emit("telemetry", {"event_id": "e1"})
        assert len(bus.messages) == 1
        assert queue.depth() == 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_transport_keeps_pending_when_bus_down_then_flushes() -> None:
    root = Path("test-artifacts") / f"nats-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        queue = EncryptedWALQueue(root / "queue.log", "queue-key-123456789012345678901234")
        failing_bus = FakeBus(succeed=False)
        client = TransportClient(queue, failing_bus)
        client.emit("risk", {"event_id": "e1"})
        assert queue.depth() == 1

        recovering_bus = FakeBus(succeed=True)
        client.bus = recovering_bus
        flushed = client.flush_pending()
        assert flushed == 1
        assert queue.depth() == 0
        assert len(recovering_bus.messages) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
