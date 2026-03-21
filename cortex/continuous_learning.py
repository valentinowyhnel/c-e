from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class GlobalReplayMemory:
    maxlen: int = 5000
    items: deque[dict[str, object]] = field(default_factory=lambda: deque(maxlen=5000))

    def add(self, item: dict[str, object]) -> None:
        self.items.append(item)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(list(self.items)) if self.items else pd.DataFrame()


class ContinuousLearningManager:
    def __init__(self) -> None:
        self.global_memory = GlobalReplayMemory()
        self.feedback_history: list[dict[str, float]] = []
        self.recent_rewards: list[float] = []

    def update_agents(self, agents: dict[str, object], new_data: pd.DataFrame) -> None:
        for agent in agents.values():
            if hasattr(agent, "update_model"):
                agent.update_model(new_data)

    def retrain_if_needed(self, episode: int, min_interval: int = 3) -> bool:
        return episode > 0 and episode % min_interval == 0

    def detect_drift(self, frame: pd.DataFrame, window: int = 120) -> bool:
        if len(frame) < window * 2:
            return False
        current = frame.tail(window)["label_attack"].mean()
        previous = frame.iloc[-window * 2 : -window]["label_attack"].mean()
        return abs(float(current - previous)) > 0.12

    def adjust_weights(self, agent_weights: dict[str, float], reward_curve: list[float]) -> dict[str, float]:
        if len(reward_curve) < 3:
            return agent_weights
        trend = float(np.mean(reward_curve[-3:]) - np.mean(reward_curve[-6:-3] or reward_curve[-3:]))
        adjusted = {}
        for name, value in agent_weights.items():
            factor = 1.03 if trend < 0 else 0.99
            adjusted[name] = max(0.05, min(1.5, value * factor))
        self.feedback_history.append(adjusted)
        return adjusted
