from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MetricsRegistry:
    counters: dict[str, float] = field(default_factory=dict)

    def inc(self, name: str, value: float = 1.0) -> None:
        self.counters[name] = self.counters.get(name, 0.0) + value

    def set(self, name: str, value: float) -> None:
        self.counters[name] = value

    def snapshot(self) -> dict[str, float]:
        return dict(self.counters)

