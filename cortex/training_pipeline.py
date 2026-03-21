from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import torch

from .agents import AnomalyAgent, GraphAgent, SentinelAgent, ThreatHunterAgent, TrustAgent
from .continuous_learning import ContinuousLearningManager
from .dataset import simulate_events
from .features import build_state, extract_features
from .graph import attach_graph_scores, build_interaction_graph
from .models import build_default_models
from .rl_sentinel import ACTIONS, SentinelRL


def _priority_from_state(state) -> float:
    return float(0.2 * state[0] + 0.2 * state[1] + 0.2 * state[3] + 0.15 * (1.0 - state[2]) + 0.15 * state[4] + 0.1 * state[5])


def build_agents() -> tuple[dict[str, object], dict[str, object]]:
    models = build_default_models()
    sentinel_rl = SentinelRL()
    agents = {
        "sentinel": SentinelAgent(sentinel_rl),
        "threat_hunter": ThreatHunterAgent("threat_hunter", models["hunter"]),
        "trust": TrustAgent("trust", models["trust"]),
        "graph": GraphAgent("graph", models["graph"]),
        "anomaly": AnomalyAgent("anomaly", models["anomaly"]),
    }
    return agents, models


def run_training(
    episodes: int = 10,
    num_events: int = 120,
    export_dir: str | Path = "cortex_exports",
) -> dict[str, object]:
    learning = ContinuousLearningManager()
    agents, models = build_agents()
    sentinel: SentinelAgent = agents["sentinel"]
    reward_curve: list[float] = []
    all_rows: list[dict[str, object]] = []
    agent_logs: list[dict[str, object]] = []
    stagnant_episodes = 0
    best_reward = float("-inf")

    for episode in range(episodes):
        episode_events = pd.DataFrame([event.__dict__ for event in simulate_events(episode=episode, num_events=num_events)])
        episode_events = attach_graph_scores(episode_events, build_interaction_graph(episode_events))
        episode_reward = 0.0
        corrected_errors = 0
        for idx, row in episode_events.iterrows():
            event = row.to_dict()
            features = extract_features(event)
            scores = {
                "anomaly_score": models["anomaly"].score(features),
                "novelty_score": features["novelty_score"],
                "trust_score": max(0.0, min(1.0, 1.0 - models["trust"].score(features))),
                "temporal_score": features["temporal_score"],
                "graph_score": models["graph"].score(features),
                "campaign_score": max(features["campaign_score"], models["hunter"].score(features)),
            }
            state = build_state(scores)
            sentinel_result = sentinel.process_event(event, state)
            ground_truth = int(event["label_attack"])
            reward = sentinel.rl.compute_reward(sentinel_result["action_id"], state, ground_truth)
            next_state = state.copy()
            sentinel.rl.store_experience(state, sentinel_result["action_id"], reward, next_state, done=idx == len(episode_events) - 1)
            episode_reward += reward

            other_results = [agents["threat_hunter"].process_event(event), agents["trust"].process_event(event), agents["graph"].process_event(event), agents["anomaly"].process_event(event)]
            predicted_attack = int(sentinel_result["action"] in {"INVESTIGATE", "ESCALATE", "BLOCK"})
            corrected_errors += int(predicted_attack == ground_truth)
            row_result = event | scores | sentinel_result | {
                "pred_attack": predicted_attack,
                "episode": episode,
                "episode_error_corrected": corrected_errors,
            }
            all_rows.append(row_result)
            for result in other_results:
                msg = agents[result["agent"]].send_message("sentinel", event["event_id"], result["score"], _priority_from_state(state), result["explanation"])
                agent_logs.append(msg.__dict__)
            learning.global_memory.add(row_result)

        loss = sentinel.rl.update_policy()
        reward_curve.append(episode_reward)
        sentinel.rl.episode_rewards.append(episode_reward)
        memory_frame = learning.global_memory.frame()
        if learning.retrain_if_needed(episode) or learning.detect_drift(memory_frame):
            learning.update_agents({k: v for k, v in agents.items() if k != "sentinel"}, memory_frame.tail(300))
        adjusted = learning.adjust_weights({name: model.weights[next(iter(model.weights))] for name, model in models.items()}, reward_curve)
        agent_logs.append({"episode": episode, "loss": loss, "episode_reward": episode_reward, "adjusted_weights": adjusted})
        if episode_reward > best_reward + 0.05:
            best_reward = episode_reward
            stagnant_episodes = 0
        else:
            stagnant_episodes += 1
        if stagnant_episodes >= 4 and episode >= 6:
            agent_logs.append({"episode": episode, "event": "early_stop", "best_reward": best_reward})
            break

    runtime_df = pd.DataFrame(all_rows)
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)
    torch.save(sentinel.rl.policy.state_dict(), export_path / "rl_sentinel.pt")
    Path(export_path / "agent_weights.json").write_text(
        json.dumps({name: getattr(agent.model, "weights", None) for name, agent in agents.items()}, indent=2),
        encoding="utf-8",
    )
    for name, agent in agents.items():
        Path(export_path / f"{name}_memory.json").write_text(json.dumps(agent.memory, indent=2), encoding="utf-8")
    runtime_df.to_csv(export_path / "simulation_results.csv", index=False)
    Path(export_path / "agent_logs.json").write_text(json.dumps(agent_logs, indent=2), encoding="utf-8")
    return {
        "runtime_df": runtime_df,
        "reward_curve": reward_curve,
        "agents": agents,
        "agent_logs": agent_logs,
        "export_dir": str(export_path),
    }
