from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HealthSnapshot:
    status: str
    queue_depth: int
    cpu_overhead: float
    memory_overhead_mb: float
    drift_hard: bool

