from __future__ import annotations

import json

from app.transport.contracts import TOPICS
from app.transport.queue import EncryptedWALQueue


class TransportClient:
    def __init__(self, queue: EncryptedWALQueue, bus=None) -> None:
        self.queue = queue
        self.bus = bus

    def emit(self, topic_key: str, payload: dict[str, object]) -> dict[str, object]:
        record = self.queue.append({"topic": TOPICS[topic_key], "payload": payload})
        if self.bus is not None:
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            if self.bus.publish(record["topic"], encoded):
                self.queue.mark_sent(str(record["record_id"]))
        return record

    def flush_pending(self) -> int:
        if self.bus is None:
            return 0
        flushed = 0
        for record in self.queue.pending():
            payload = record.get("payload", {})
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            if self.bus.publish(str(record["topic"]), encoded):
                self.queue.mark_sent(str(record["record_id"]))
                flushed += 1
        return flushed

    async def flush_pending_async(self) -> int:
        if self.bus is None or not hasattr(self.bus, "publish_async"):
            return self.flush_pending()
        flushed = 0
        for record in self.queue.pending():
            payload = record.get("payload", {})
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            if await self.bus.publish_async(str(record["topic"]), encoded):
                self.queue.mark_sent(str(record["record_id"]))
                flushed += 1
        return flushed
