from __future__ import annotations

from collections import deque
import statistics

from app.models import DriftStatus


class ADWINLike:
    def __init__(self, max_window: int = 64, delta: float = 0.2) -> None:
        self.window: deque[float] = deque(maxlen=max_window)
        self.delta = delta

    def update(self, value: float) -> tuple[bool, float]:
        self.window.append(value)
        if len(self.window) < 8:
            return False, statistics.fmean(self.window)
        midpoint = len(self.window) // 2
        first = list(self.window)[:midpoint]
        second = list(self.window)[midpoint:]
        mean_a = statistics.fmean(first)
        mean_b = statistics.fmean(second)
        return abs(mean_a - mean_b) > self.delta, statistics.fmean(self.window)


class PageHinkley:
    def __init__(self, threshold: float = 0.25, alpha: float = 0.99) -> None:
        self.mean = 0.0
        self.cumulative = 0.0
        self.min_cumulative = 0.0
        self.count = 0
        self.threshold = threshold
        self.alpha = alpha

    def update(self, value: float) -> tuple[bool, float]:
        self.count += 1
        self.mean = self.mean + (value - self.mean) / self.count
        self.cumulative = self.alpha * self.cumulative + value - self.mean
        self.min_cumulative = min(self.min_cumulative, self.cumulative)
        return (self.cumulative - self.min_cumulative) > self.threshold, self.mean


class DriftDetectorSuite:
    def __init__(self) -> None:
        self.adwin = ADWINLike()
        self.page_hinkley = PageHinkley()

    def evaluate(self, score: float, feature_mean: float) -> DriftStatus:
        adwin_trigger, adwin_mean = self.adwin.update(feature_mean)
        ph_trigger, ph_mean = self.page_hinkley.update(score)
        reasons: list[str] = []
        if adwin_trigger:
            reasons.append("distribution_shift")
        if ph_trigger:
            reasons.append("score_shift")
        return DriftStatus(
            soft_drift=adwin_trigger or ph_trigger,
            hard_drift=adwin_trigger and ph_trigger,
            adwin_mean=round(adwin_mean, 4),
            page_hinkley_mean=round(ph_mean, 4),
            reasons=reasons,
        )

