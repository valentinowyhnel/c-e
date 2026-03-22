from __future__ import annotations

import numpy as np

from cortex.rl_sentinel import SentinelRL


def test_reward_prefers_strong_response_on_critical_attack() -> None:
    rl = SentinelRL()
    critical_attack = np.array([0.92, 0.86, 0.18, 0.78, 0.88, 0.84], dtype=np.float32)
    context = {"blast_radius": 0.9, "asset_criticality": 0.95, "crown_jewel": True}
    escalate = rl.compute_reward(3, critical_attack, ground_truth=1, context=context)
    ignore = rl.compute_reward(0, critical_attack, ground_truth=1, context=context)
    assert escalate > ignore
    assert escalate > 0.4


def test_reward_penalizes_block_on_benign_signal() -> None:
    rl = SentinelRL()
    benign = np.array([0.08, 0.05, 0.93, 0.07, 0.09, 0.04], dtype=np.float32)
    context = {"blast_radius": 0.85, "asset_criticality": 0.9, "crown_jewel": True}
    block = rl.compute_reward(4, benign, ground_truth=0, context=context)
    ignore = rl.compute_reward(0, benign, ground_truth=0, context=context)
    assert ignore > block
    assert block < 0.0


def test_reward_prefers_light_response_for_low_risk_benign() -> None:
    rl = SentinelRL()
    benign = np.array([0.15, 0.12, 0.88, 0.10, 0.11, 0.09], dtype=np.float32)
    context = {"blast_radius": 0.2, "asset_criticality": 0.25, "crown_jewel": False}
    monitor = rl.compute_reward(1, benign, ground_truth=0, context=context)
    investigate = rl.compute_reward(2, benign, ground_truth=0, context=context)
    assert monitor > investigate


def test_reward_increases_escalation_value_for_high_blast_radius_attack() -> None:
    rl = SentinelRL()
    attack = np.array([0.82, 0.74, 0.22, 0.68, 0.77, 0.73], dtype=np.float32)
    low_context = {"blast_radius": 0.2, "asset_criticality": 0.3, "crown_jewel": False}
    high_context = {"blast_radius": 0.95, "asset_criticality": 0.95, "crown_jewel": True}
    low_reward = rl.compute_reward(3, attack, ground_truth=1, context=low_context)
    high_reward = rl.compute_reward(3, attack, ground_truth=1, context=high_context)
    assert high_reward > low_reward
