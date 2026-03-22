from __future__ import annotations

import numpy as np

from cortex.rl_sentinel import SentinelRL


def test_reward_prefers_strong_response_on_critical_attack() -> None:
    rl = SentinelRL()
    critical_attack = np.array([0.92, 0.86, 0.18, 0.78, 0.88, 0.84], dtype=np.float32)
    escalate = rl.compute_reward(3, critical_attack, ground_truth=1)
    ignore = rl.compute_reward(0, critical_attack, ground_truth=1)
    assert escalate > ignore
    assert escalate > 0.4


def test_reward_penalizes_block_on_benign_signal() -> None:
    rl = SentinelRL()
    benign = np.array([0.08, 0.05, 0.93, 0.07, 0.09, 0.04], dtype=np.float32)
    block = rl.compute_reward(4, benign, ground_truth=0)
    ignore = rl.compute_reward(0, benign, ground_truth=0)
    assert ignore > block
    assert block < 0.0


def test_reward_prefers_light_response_for_low_risk_benign() -> None:
    rl = SentinelRL()
    benign = np.array([0.15, 0.12, 0.88, 0.10, 0.11, 0.09], dtype=np.float32)
    monitor = rl.compute_reward(1, benign, ground_truth=0)
    investigate = rl.compute_reward(2, benign, ground_truth=0)
    assert monitor > investigate
