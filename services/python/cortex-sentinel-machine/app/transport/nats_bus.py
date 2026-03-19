from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Thread
from typing import Any, Callable


try:
    import nats
except ImportError:  # pragma: no cover
    nats = None


JETSTREAM_SUBJECTS = [
    "cortex.obs.stream",
    "cortex.trust.updates",
    "cortex.security.events",
    "cortex.obs.anomalies",
    "cortex.sentinel.commands",
]


class NATSJetStreamBus:
    def __init__(self, url: str, connect_timeout_seconds: float = 0.2) -> None:
        self.url = url
        self.connect_timeout_seconds = connect_timeout_seconds
        self.loop = asyncio.new_event_loop()
        self.thread: Thread | None = None
        self.nc: Any | None = None
        self.js: Any | None = None

    @property
    def available(self) -> bool:
        return nats is not None

    def start(self) -> bool:
        if not self.available:
            return False
        if self.nc is not None:
            return True
        if self.thread is None:
            self.thread = Thread(target=self._run_loop, daemon=True)
            self.thread.start()
        self.nc = self._submit(
            nats.connect(
                self.url,
                connect_timeout=self.connect_timeout_seconds,
                allow_reconnect=False,
                max_reconnect_attempts=0,
            )
        )
        self.js = self.nc.jetstream()
        self._submit(self._ensure_stream())
        return True

    def stop(self) -> None:
        if self.nc is not None:
            self._submit(self.nc.drain())
            self.nc = None
            self.js = None
        if self.thread is not None:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=2)
            self.thread = None

    def publish(self, subject: str, payload: bytes) -> bool:
        if not self.available:
            return False
        if self.nc is None:
            self.start()
        try:
            self._submit(self.publish_async(subject, payload))
            return True
        except Exception:
            return False

    def subscribe(self, subject: str, cb: Callable[..., Any], durable: str) -> bool:
        if not self.available:
            return False
        if self.nc is None:
            self.start()
        try:
            self._submit(self.js.subscribe(subject, cb=cb, durable=durable))
            return True
        except Exception:
            self._submit(self.nc.subscribe(subject, cb=cb))
            return True

    async def _ensure_stream(self) -> None:
        try:
            await self.js.stream_info("CORTEX_EVENTS")
        except Exception:
            await self.js.add_stream(name="CORTEX_EVENTS", subjects=JETSTREAM_SUBJECTS)

    async def publish_async(self, subject: str, payload: bytes) -> bool:
        try:
            await self.js.publish(subject, payload)
            return True
        except Exception:
            try:
                await self.nc.publish(subject, payload)
                return True
            except Exception:
                return False

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _submit(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        try:
            return future.result(timeout=max(1.0, self.connect_timeout_seconds + 1.0))
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError("nats_operation_timeout") from exc
