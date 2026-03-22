from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ACTIONS = ["IGNORE", "MONITOR", "INVESTIGATE", "ESCALATE", "BLOCK"]


class QNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


@dataclass
class Experience:
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


class ReplayBuffer:
    def __init__(self, capacity: int = 4096) -> None:
        self.buffer: deque[Experience] = deque(maxlen=capacity)

    def add(self, experience: Experience) -> None:
        self.buffer.append(experience)

    def sample(self, batch_size: int) -> list[Experience]:
        return random.sample(self.buffer, batch_size)

    def __len__(self) -> int:
        return len(self.buffer)


class SentinelRL:
    def __init__(
        self,
        state_dim: int = 6,
        action_dim: int = 5,
        gamma: float = 0.97,
        lr: float = 1e-3,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.992,
        epsilon_min: float = 0.05,
        device: str | None = None,
    ) -> None:
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.policy = QNetwork(state_dim, action_dim).to(self.device)
        self.target = QNetwork(state_dim, action_dim).to(self.device)
        self.target.load_state_dict(self.policy.state_dict())
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=lr)
        self.buffer = ReplayBuffer()
        self.losses: list[float] = []
        self.episode_rewards: list[float] = []

    def select_action(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randrange(self.action_dim)
        with torch.no_grad():
            q_values = self.policy(torch.tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0))
            return int(torch.argmax(q_values, dim=1).item())

    def store_experience(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool = False,
    ) -> None:
        self.buffer.add(Experience(state, action, reward, next_state, done))

    @staticmethod
    def _action_strength(action: int) -> float:
        return [0.0, 0.25, 0.5, 0.8, 1.0][action]

    @staticmethod
    def _action_cost(action: int) -> float:
        return [0.0, 0.05, 0.12, 0.24, 0.42][action]

    def compute_reward(self, action: int, state: np.ndarray, ground_truth: int) -> float:
        anomaly, novelty, trust, temporal, graph, campaign = [float(x) for x in state]
        trust_risk = 1.0 - trust
        attack_pressure = 0.24 * anomaly + 0.18 * novelty + 0.18 * trust_risk + 0.14 * temporal + 0.14 * graph + 0.12 * campaign
        criticality = 0.55 * graph + 0.45 * campaign
        early_signal = 0.55 * novelty + 0.45 * temporal
        action_strength = self._action_strength(action)
        action_cost = self._action_cost(action)

        if ground_truth == 1:
            target_strength = min(1.0, 0.20 + 0.72 * attack_pressure + 0.18 * criticality)
            alignment_bonus = 1.55 - 1.90 * (action_strength - target_strength) ** 2
            early_bonus = 0.35 * early_signal * max(0.0, action_strength - 0.20)
            miss_penalty = 1.25 * max(0.0, target_strength - action_strength) ** 2
            underreaction_penalty = 0.55 * criticality * max(0.0, 0.75 - action_strength)
            reward = alignment_bonus + early_bonus - miss_penalty - underreaction_penalty - action_cost
        else:
            benign_budget = max(0.0, 0.06 + 0.18 * attack_pressure)
            alignment_bonus = 0.92 - 1.20 * (action_strength - benign_budget) ** 2
            false_positive_penalty = 1.55 * max(0.0, action_strength - benign_budget) ** 2
            heavy_action_penalty = 0.55 * max(0.0, action_strength - 0.35) ** 2
            reward = alignment_bonus - false_positive_penalty - heavy_action_penalty - 0.8 * action_cost

        return float(np.clip(reward, -2.5, 2.5))

    def update_policy(self, batch_size: int = 64) -> float:
        if len(self.buffer) < batch_size:
            return 0.0
        batch = self.buffer.sample(batch_size)
        states = torch.tensor(np.array([exp.state for exp in batch]), dtype=torch.float32, device=self.device)
        actions = torch.tensor([exp.action for exp in batch], dtype=torch.int64, device=self.device)
        rewards = torch.tensor([exp.reward for exp in batch], dtype=torch.float32, device=self.device)
        next_states = torch.tensor(np.array([exp.next_state for exp in batch]), dtype=torch.float32, device=self.device)
        dones = torch.tensor([exp.done for exp in batch], dtype=torch.float32, device=self.device)

        q_values = self.policy(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            max_next = self.target(next_states).max(dim=1).values
            targets = rewards + self.gamma * max_next * (1.0 - dones)

        loss = F.smooth_l1_loss(q_values, targets)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(), max_norm=1.0)
        self.optimizer.step()
        self.target.load_state_dict(self.policy.state_dict())
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        loss_value = float(loss.item())
        self.losses.append(loss_value)
        return loss_value
