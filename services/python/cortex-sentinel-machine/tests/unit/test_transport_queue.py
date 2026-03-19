from pathlib import Path
import shutil
import uuid

from app.transport.queue import EncryptedWALQueue


def test_queue_marks_record_sent() -> None:
    root = Path("test-artifacts") / f"queue-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        queue = EncryptedWALQueue(root / "queue.log", "queue-key-123456789012345678901234")
        record = queue.append({"topic": "cortex.obs.stream", "payload": {"x": 1}})
        assert queue.depth() == 1
        queue.mark_sent(str(record["record_id"]))
        assert queue.depth() == 0
    finally:
        shutil.rmtree(root, ignore_errors=True)

