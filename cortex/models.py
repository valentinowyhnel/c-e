from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class OnlineStatsModel:
    """Lightweight online model used to keep Colab execution simple and stable."""

    weights: dict[str, float]
    lr: float = 0.03
    history: list[dict[str, float]] = field(default_factory=list)

    def score(self, event: dict[str, float]) -> float:
        total = 0.0
        for name, weight in self.weights.items():
            total += weight * float(event.get(name, 0.0))
        return max(0.0, min(1.0, total))

    def update(self, events: pd.DataFrame) -> None:
        if events.empty:
            return
        attack_df = events.loc[events["label_attack"] == 1]
        benign_df = events.loc[events["label_attack"] == 0]
        if benign_df.empty:
            benign_df = events
        for name in list(self.weights):
            attack_mean = float(attack_df[name].mean()) if not attack_df.empty else 0.0
            benign_mean = float(benign_df[name].mean()) if not benign_df.empty else 0.0
            delta = attack_mean - benign_mean
            self.weights[name] = max(0.01, min(1.5, self.weights[name] + self.lr * delta))
        self.history.append(dict(self.weights))


def build_default_models() -> dict[str, OnlineStatsModel]:
    return {
        "anomaly": OnlineStatsModel({"anomaly_score": 0.65, "novelty_score": 0.15, "temporal_score": 0.10, "campaign_score": 0.10}),
        "trust": OnlineStatsModel({"trust_risk": 0.70, "novelty_score": 0.10, "graph_score": 0.10, "campaign_score": 0.10}),
        "graph": OnlineStatsModel({"graph_score": 0.55, "temporal_score": 0.15, "campaign_score": 0.20, "anomaly_score": 0.10}),
        "hunter": OnlineStatsModel({"novelty_score": 0.55, "anomaly_score": 0.20, "campaign_score": 0.15, "graph_score": 0.10}),
    }
