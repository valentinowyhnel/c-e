from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import fabs
import random
import statistics

from app.models import DriftStatus, NormalizedEvent, RiskScore


@dataclass(slots=True)
class ProjectionTree:
    weights: list[float]
    offset: float

    def score(self, values: list[float]) -> float:
        projection = sum(weight * value for weight, value in zip(self.weights, values, strict=False)) + self.offset
        return 1.0 / (1.0 + abs(projection))


class OnlineHalfSpaceForest:
    def __init__(self, dimensions: int, trees: int = 12, seed: int = 13) -> None:
        rng = random.Random(seed)
        self.trees = [
            ProjectionTree(
                weights=[rng.uniform(-1.0, 1.0) for _ in range(dimensions)],
                offset=rng.uniform(-0.5, 0.5),
            )
            for _ in range(trees)
        ]
        self.reference: deque[float] = deque(maxlen=512)

    def score(self, vector: dict[str, float]) -> float:
        values = list(vector.values())
        density = statistics.fmean(tree.score(values) for tree in self.trees)
        self.reference.append(density)
        baseline = statistics.fmean(self.reference) if self.reference else density
        return max(0.0, min(1.0, 1.0 - density / max(baseline, 1e-6)))


class RobustDeviationScorer:
    def __init__(self) -> None:
        self.history: dict[str, deque[float]] = {}

    def score(self, vector: dict[str, float]) -> float:
        deviations: list[float] = []
        for key, value in vector.items():
            series = self.history.setdefault(key, deque(maxlen=256))
            series.append(value)
            median = statistics.median(series)
            mad = statistics.median([fabs(item - median) for item in series]) if len(series) > 1 else 0.0
            deviations.append(fabs(value - median) / max(mad * 1.4826, 0.05))
        return max(0.0, min(1.0, statistics.fmean(deviations) / 6.0))


class SeverityCalibrator:
    def calibrate(self, local_score: float, context: dict[str, object], drift: DriftStatus) -> RiskScore:
        score = local_score
        reasons: list[str] = []
        if context.get("maintenance_window"):
            score *= 0.7
            reasons.append("maintenance_window")
        if not context.get("software_inventory_match", True):
            score *= 1.15
            reasons.append("inventory_mismatch")
        if drift.soft_drift:
            score *= 1.05
            reasons.append("soft_drift")
        if drift.hard_drift:
            score *= 1.2
            reasons.append("hard_drift")
        score = max(0.0, min(1.0, score))
        if score >= 0.9:
            severity = "critical"
        elif score >= 0.75:
            severity = "high-risk"
        elif score >= 0.45:
            severity = "suspicious"
        else:
            severity = "info"
        confidence = max(0.05, min(0.99, 1.0 - (0.15 if drift.hard_drift else 0.0)))
        return RiskScore(score=round(score, 4), severity=severity, confidence=round(confidence, 4), reasons=reasons)


class LocalScoringPipeline:
    def __init__(self, dimensions: int) -> None:
        self.primary = OnlineHalfSpaceForest(dimensions=dimensions)
        self.secondary = RobustDeviationScorer()
        self.calibrator = SeverityCalibrator()

    def score(self, event: NormalizedEvent, drift_status: DriftStatus) -> RiskScore:
        primary = self.primary.score(event.feature_vector)
        secondary = self.secondary.score(event.feature_vector)
        combined = (primary * 0.65) + (secondary * 0.35)
        event.confidence_local = round(1.0 - abs(primary - secondary), 4)
        return self.calibrator.calibrate(combined, event.context, drift_status)
