from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import fmean
import uuid

from app.models import ModelSnapshot, NormalizedEvent, stable_hash


@dataclass(slots=True)
class MemoryBank:
    short_term: deque[dict[str, float]]
    long_term: deque[dict[str, float]]


class LocalTrainer:
    def __init__(self, tenant_id: str, machine_id: str, class_scope: str = "default") -> None:
        self.tenant_id = tenant_id
        self.machine_id = machine_id
        self.class_scope = class_scope
        self.memory = MemoryBank(short_term=deque(maxlen=64), long_term=deque(maxlen=512))
        self.shadow_counter = 0

    def observe(self, event: NormalizedEvent) -> None:
        self.memory.short_term.append(event.feature_vector.copy())
        self.memory.long_term.append(event.feature_vector.copy())

    def can_train(self, min_support: int) -> bool:
        return len(self.memory.short_term) >= min_support and len(self.memory.long_term) >= min_support

    def train_shadow(self, parent: ModelSnapshot | None) -> ModelSnapshot:
        self.shadow_counter += 1
        baseline = self._centroid(self.memory.long_term)
        recent = self._centroid(self.memory.short_term)
        delta = {key: round(recent.get(key, 0.0) - baseline.get(key, 0.0), 6) for key in sorted(set(baseline) | set(recent))}
        parameters = {
            "baseline_centroid": baseline,
            "recent_centroid": recent,
            "delta": delta,
            "learning_rate_cap": 0.05,
            "gradient_clip_norm": 1.0,
        }
        return ModelSnapshot(
            model_id=f"shadow-{self.shadow_counter}-{uuid.uuid4().hex[:8]}",
            parent_model_id=parent.model_id if parent else None,
            tenant_scope=self.tenant_id,
            machine_scope=self.machine_id,
            class_scope=self.class_scope,
            training_window=f"short={len(self.memory.short_term)},long={len(self.memory.long_term)}",
            feature_schema_hash=stable_hash(sorted(parameters["delta"].keys())),
            signed_manifest={},
            evaluation_report={},
            rollback_pointer=parent.model_id if parent else None,
            parameters=parameters,
        )

    def _centroid(self, rows: deque[dict[str, float]]) -> dict[str, float]:
        keys = sorted({key for row in rows for key in row})
        return {key: round(fmean(row.get(key, 0.0) for row in rows), 6) for key in keys}

