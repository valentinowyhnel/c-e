from __future__ import annotations

from typing import Protocol

from app.models import RawEvent


class Collector(Protocol):
    def collect(self) -> list[RawEvent]:
        ...

