from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .features import extract_features
from .models import OnlineStatsModel
from .rl_sentinel import ACTIONS, SentinelRL


@dataclass
class AgentMessage:
    sender: str
    receiver: str
    event_id: str
    risk_signal: float
    priority: float
    explanation: str


@dataclass
class BaseAgent:
    name: str
    model: OnlineStatsModel | None = None
    memory: list[dict[str, object]] = field(default_factory=list)

    def update_model(self, data: pd.DataFrame) -> None:
        if self.model is not None:
            self.model.update(data)

    def process_event(self, event: dict[str, object]) -> dict[str, object]:
        features = extract_features(event)
        score = self.model.score(features) if self.model else 0.0
        result = {"agent": self.name, "score": score, "explanation": f"{self.name} scored the event."}
        self.memory.append(result | {"event_id": event["event_id"]})
        return result

    def send_message(self, receiver: str, event_id: str, risk_signal: float, priority: float, explanation: str) -> AgentMessage:
        return AgentMessage(
            sender=self.name,
            receiver=receiver,
            event_id=event_id,
            risk_signal=float(risk_signal),
            priority=float(priority),
            explanation=explanation,
        )


class ThreatHunterAgent(BaseAgent):
    pass


class TrustAgent(BaseAgent):
    pass


class GraphAgent(BaseAgent):
    pass


class AnomalyAgent(BaseAgent):
    pass


class SentinelAgent(BaseAgent):
    def __init__(self, rl: SentinelRL) -> None:
        super().__init__(name="sentinel", model=None)
        self.rl = rl
        self.action_history: list[int] = []

    def process_event(self, event: dict[str, object], state) -> dict[str, object]:
        action = self.rl.select_action(state)
        risk_signal = float(sum(state[[0, 1, 3, 4, 5]]) / 5.0)
        priority = float(0.2 * state[0] + 0.2 * state[1] + 0.2 * state[3] + 0.15 * (1.0 - state[2]) + 0.15 * state[4] + 0.1 * state[5])
        self.action_history.append(action)
        result = {
            "agent": self.name,
            "action": ACTIONS[action],
            "action_id": action,
            "risk_signal": risk_signal,
            "priority": priority,
            "explanation": f"Sentinel selected {ACTIONS[action]}",
        }
        self.memory.append(result | {"event_id": event["event_id"]})
        return result

