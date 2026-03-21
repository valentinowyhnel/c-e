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

    def compute_reward(self, action: int, state: np.ndarray, ground_truth: int) -> float:
        risk = float((state[0] + state[1] + (1.0 - state[2]) + state[3] + state[4] + state[5]) / 6.0)
        if ground_truth == 1:
            if action in {2, 3, 4}:
                return 1.4 + risk
            if action == 1:
                return 0.35 + 0.3 * risk
            return -1.15
        if action == 0:
            return 0.55 - 0.2 * risk
        if action == 1:
            return 0.18 - 0.05 * risk
        return -0.7 - 0.3 * risk

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

