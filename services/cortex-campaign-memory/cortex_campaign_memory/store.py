from __future__ import annotations

import time
from collections import defaultdict

from .models import AggregationWindow, CampaignEventFingerprint, CampaignSignal

WINDOWS = {
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "30d": 30 * 24 * 3600,
    "90d": 90 * 24 * 3600,
}


class CampaignMemoryStore:
    def __init__(self) -> None:
        self._events: list[CampaignEventFingerprint] = []
        self._by_identity: dict[str, list[CampaignEventFingerprint]] = defaultdict(list)
        self._by_path: dict[str, list[CampaignEventFingerprint]] = defaultdict(list)
        self._by_resource_family: dict[str, list[CampaignEventFingerprint]] = defaultdict(list)

    def clear(self) -> None:
        self._events.clear()
        self._by_identity.clear()
        self._by_path.clear()
        self._by_resource_family.clear()

    def store_event_fingerprint(self, event: CampaignEventFingerprint) -> CampaignEventFingerprint:
        self._events.append(event)
        self._by_identity[event.identity_id].append(event)
        self._by_path[event.path_id].append(event)
        self._by_resource_family[event.resource_family].append(event)
        self._prune()
        return event

    def aggregate_by_identity(self, identity_id: str) -> list[AggregationWindow]:
        return self._aggregate(self._by_identity.get(identity_id, []))

    def aggregate_by_path(self, path_id: str | None) -> list[AggregationWindow]:
        if not path_id:
            return []
        return self._aggregate(self._by_path.get(path_id, []))

    def aggregate_by_resource_family(self, resource_family: str | None) -> list[AggregationWindow]:
        if not resource_family:
            return []
        return self._aggregate(self._by_resource_family.get(resource_family, []))

    def progressive_deviation_score(
        self,
        identity_id: str,
        path_id: str | None = None,
        resource_family: str | None = None,
    ) -> tuple[float, list[AggregationWindow], list[str]]:
        windows = self.aggregate_by_identity(identity_id)
        path_windows = self.aggregate_by_path(path_id)
        resource_windows = self.aggregate_by_resource_family(resource_family)
        evidence: list[str] = []

        score = 0.0
        if windows:
            last_30d = next((window for window in windows if window.window == "30d"), None)
            last_90d = next((window for window in windows if window.window == "90d"), None)
            if last_30d and last_30d.count >= 3 and last_30d.weak_signal_sum >= 90:
                score += 35.0
                evidence.append("identity weak-signal accumulation exceeds 30d low-and-slow threshold")
            if last_90d and last_90d.count >= 5:
                score += 15.0
                evidence.append("identity shows persistent low-and-slow behavior over 90d")
        if path_windows:
            hot_path = next((window for window in path_windows if window.window == "30d"), None)
            if hot_path and hot_path.novelty_avg >= 55:
                score += 20.0
                evidence.append("network path remains novel over 30d")
        if resource_windows:
            hot_resource = next((window for window in resource_windows if window.window == "30d"), None)
            if hot_resource and hot_resource.anomaly_avg >= 45:
                score += 15.0
                evidence.append("resource family anomaly remains elevated over 30d")

        deduped_windows = self._merge_windows(windows, path_windows, resource_windows)
        return min(100.0, round(score, 2)), deduped_windows, evidence

    def campaign_likelihood_score(
        self,
        identity_id: str,
        path_id: str | None = None,
        resource_family: str | None = None,
        trace_id: str = "",
        correlation_id: str | None = None,
    ) -> CampaignSignal:
        progressive_score, windows, evidence = self.progressive_deviation_score(identity_id, path_id, resource_family)
        density = sum(window.count for window in windows if window.window in {"7d", "30d"}) * 2.5
        novelty_pressure = sum(window.novelty_avg for window in windows if window.window in {"30d", "90d"}) * 0.12
        anomaly_pressure = sum(window.anomaly_avg for window in windows if window.window in {"7d", "30d"}) * 0.18
        likelihood = min(100.0, round(progressive_score + density + novelty_pressure + anomaly_pressure, 2))
        confidence = min(0.95, round(0.35 + 0.08 * len(evidence) + 0.03 * min(5, len(windows)), 2))
        if likelihood >= 70 and "campaign likelihood exceeds escalation threshold" not in evidence:
            evidence.append("campaign likelihood exceeds escalation threshold")
        return CampaignSignal(
            identity_id=identity_id,
            path_id=path_id,
            resource_family=resource_family,
            progressive_deviation_score=progressive_score,
            campaign_likelihood_score=likelihood,
            windows=windows,
            evidence=evidence,
            confidence=confidence,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )

    def _aggregate(self, events: list[CampaignEventFingerprint]) -> list[AggregationWindow]:
        now = time.time()
        windows: list[AggregationWindow] = []
        for label, seconds in WINDOWS.items():
            scoped = [event for event in events if now - event.timestamp <= seconds]
            if not scoped:
                windows.append(
                    AggregationWindow(
                        window=label,
                        count=0,
                        weak_signal_sum=0.0,
                        novelty_avg=0.0,
                        anomaly_avg=0.0,
                    )
                )
                continue
            windows.append(
                AggregationWindow(
                    window=label,
                    count=len(scoped),
                    weak_signal_sum=round(sum(item.weak_signal_score for item in scoped), 2),
                    novelty_avg=round(sum(item.novelty_score for item in scoped) / len(scoped), 2),
                    anomaly_avg=round(sum(item.anomaly_score for item in scoped) / len(scoped), 2),
                )
            )
        return windows

    def _merge_windows(self, *groups: list[AggregationWindow]) -> list[AggregationWindow]:
        merged: dict[str, AggregationWindow] = {}
        for group in groups:
            for item in group:
                current = merged.get(item.window)
                if current is None:
                    merged[item.window] = item.model_copy()
                    continue
                merged[item.window] = AggregationWindow(
                    window=item.window,
                    count=max(current.count, item.count),
                    weak_signal_sum=max(current.weak_signal_sum, item.weak_signal_sum),
                    novelty_avg=max(current.novelty_avg, item.novelty_avg),
                    anomaly_avg=max(current.anomaly_avg, item.anomaly_avg),
                )
        return [merged[label] for label in WINDOWS if label in merged]

    def _prune(self) -> None:
        cutoff = time.time() - WINDOWS["90d"]
        self._events = [event for event in self._events if event.timestamp >= cutoff]
        for mapping in (self._by_identity, self._by_path, self._by_resource_family):
            for key in list(mapping):
                mapping[key] = [event for event in mapping[key] if event.timestamp >= cutoff]
                if not mapping[key]:
                    del mapping[key]
