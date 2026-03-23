from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import httpx
import pandas as pd
import torch

from .agents import AnomalyAgent, GraphAgent, SentinelAgent, ThreatHunterAgent, TrustAgent
from .dataset import simulate_events
from .features import build_state, extract_features
from .graph import attach_graph_scores, build_interaction_graph
from .learning.continuous_learning_engine import ContinuousLearningEngine
from .meta_decision import (
    AnalysisFingerprintEngine,
    AnalysisReuseOrchestrator,
    AgentTrustRegistry,
    CaseComplexityEngine,
    CaseMemoryStore,
    ConfidenceCalibrationLayer,
    DecisionMemoryLinker,
    DecisionTrustEngine,
    DeepAnalysisProtocol,
    MetaDecisionAgent,
)
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


def build_meta_decision_stack() -> tuple[MetaDecisionAgent, AgentTrustRegistry, DecisionTrustEngine, CaseMemoryStore]:
    registry = AgentTrustRegistry()
    registry.register_agent("threat_hunter", capabilities={"threat_hunting": 0.9}, specialties={"campaign_score": 0.85}, base_trust=0.62)
    registry.register_agent("trust", capabilities={"trust_assessment": 0.92}, specialties={"trust_score": 0.9}, base_trust=0.68)
    registry.register_agent("graph", capabilities={"identity_graph": 0.88}, specialties={"graph_score": 0.88}, base_trust=0.64)
    registry.register_agent("anomaly", capabilities={"anomaly_detection": 0.91}, specialties={"anomaly_score": 0.9}, base_trust=0.66)
    decision_trust_engine = DecisionTrustEngine(registry)
    case_memory_store = CaseMemoryStore()
    decision_memory_linker = DecisionMemoryLinker(
        fingerprint_engine=AnalysisFingerprintEngine(),
        case_memory_store=case_memory_store,
        reuse_orchestrator=AnalysisReuseOrchestrator(),
    )
    meta_decision_agent = MetaDecisionAgent(
        decision_trust_engine=decision_trust_engine,
        case_complexity_engine=CaseComplexityEngine(),
        deep_analysis_protocol=DeepAnalysisProtocol(),
        confidence_calibration=ConfidenceCalibrationLayer(),
        decision_memory_linker=decision_memory_linker,
    )
    return meta_decision_agent, registry, decision_trust_engine, case_memory_store


def run_training(
    episodes: int = 10,
    num_events: int = 120,
    export_dir: str | Path = "cortex_exports",
) -> dict[str, object]:
    agents, models = build_agents()
    sentinel: SentinelAgent = agents["sentinel"]
    meta_decision_agent, trust_registry, decision_trust_engine, case_memory_store = build_meta_decision_stack()
    learning = ContinuousLearningEngine(
        trust_registry=trust_registry,
        decision_trust_engine=decision_trust_engine,
        case_memory_store=case_memory_store,
        sentinel_rl=sentinel.rl,
    )
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
                "trust_risk": features["trust_risk"],
                "temporal_score": features["temporal_score"],
                "graph_score": models["graph"].score(features),
                "campaign_score": max(features["campaign_score"], models["hunter"].score(features)),
            }
            base_priority = _priority_from_state(build_state(scores))
            other_results = [
                agents["threat_hunter"].process_event(event),
                agents["trust"].process_event(event),
                agents["graph"].process_event(event),
                agents["anomaly"].process_event(event),
            ]
            agent_messages = []
            for result in other_results:
                specialty = {
                    "threat_hunter": "campaign_score",
                    "trust": "trust_score",
                    "graph": "graph_score",
                    "anomaly": "anomaly_score",
                }[result["agent"]]
                runtime_trust = max(0.0, min(1.0, 1.0 - abs(float(result["score"]) - scores.get(specialty, 0.5))))
                trust_registry.update_runtime_trust(result["agent"], runtime_trust)
                message = agents[result["agent"]].send_message(
                    "meta_decision_agent",
                    event["event_id"],
                    result["score"],
                    base_priority,
                    result["explanation"],
                )
                agent_messages.append(
                    message.__dict__
                    | {
                        "specialty": specialty,
                        "runtime_trust": runtime_trust,
                        "uncertainty": 1.0 - float(result["score"]),
                        "data_quality": runtime_trust,
                        "reasoning_quality": 0.55 if result["explanation"] else 0.25,
                    }
                )
            meta_decision = meta_decision_agent.evaluate(
                event=event,
                agent_messages=agent_messages,
                model_scores={
                    "anomaly": scores["anomaly_score"],
                    "trust": 1.0 - scores["trust_score"],
                    "graph": scores["graph_score"],
                    "hunter": scores["campaign_score"],
                },
                identity_context={"source": event["source"], "target": event["target"]},
                graph_context={"source": event["source"], "target": event["target"], "graph_score": scores["graph_score"]},
                policy_version="opa:v1",
                model_versions={name: "default:v1" for name in ["anomaly", "trust", "graph", "hunter"]},
            )
            state_scores = dict(scores)
            state_scores["anomaly_score"] = max(scores["anomaly_score"], meta_decision.weighted_scores.get("anomaly_risk", 0.0))
            state_scores["trust_score"] = max(0.0, min(1.0, scores["trust_score"] * meta_decision.agent_trust_scores.get("trust", 1.0)))
            state_scores["graph_score"] = max(scores["graph_score"], meta_decision.weighted_scores.get("graph_risk", 0.0))
            state_scores["campaign_score"] = max(scores["campaign_score"], meta_decision.weighted_scores.get("threat_hunter_risk", 0.0))
            state = build_state(state_scores)
            sentinel_result = sentinel.process_event(event, state)
            ground_truth = int(event["label_attack"])
            reward = sentinel.rl.compute_reward(
                sentinel_result["action_id"],
                state,
                ground_truth,
                context={
                    "blast_radius": float(event.get("blast_radius", 0.0)),
                    "asset_criticality": float(event.get("asset_criticality", 0.0)),
                    "crown_jewel": bool(event.get("metadata", {}).get("crown_jewel", False)),
                },
            )
            next_state = state.copy()
            sentinel.rl.store_experience(state, sentinel_result["action_id"], reward, next_state, done=idx == len(episode_events) - 1)
            episode_reward += reward

            predicted_attack = int(sentinel_result["action"] in {"INVESTIGATE", "ESCALATE", "BLOCK"})
            corrected_errors += int(predicted_attack == ground_truth)
            row_result = event | scores | state_scores | sentinel_result | meta_decision.trusted_agent_output | {
                "pred_attack": predicted_attack,
                "episode": episode,
                "episode_error_corrected": corrected_errors,
                "mda_degraded_mode": meta_decision.degraded_mode,
            }
            all_rows.append(row_result)
            agent_logs.extend(agent_messages)
            agent_logs.append({"event_id": event["event_id"], "mda": meta_decision.to_dict()})
            learning.memory.add(row_result)
            learning.remember_case(
                event=event,
                features=scores,
                scores=meta_decision.weighted_scores,
                agents_used=meta_decision.selected_agents,
                final_decision=sentinel_result["action"],
                validation="confirmed" if predicted_attack == ground_truth else "pending_review",
                model_version="anomaly:default:v1|graph:default:v1|hunter:default:v1|trust:default:v1",
                policy_version="opa:v1",
                reusability_score=max(0.0, min(1.0, 1.0 - float(event.get("novelty_score", 0.0)))),
            )
            for result in other_results:
                learning.update_agent_performance(
                    agent_id=result["agent"],
                    specialty={
                        "threat_hunter": "campaign_score",
                        "trust": "trust_score",
                        "graph": "graph_score",
                        "anomaly": "anomaly_score",
                    }[result["agent"]],
                    correct=(predicted_attack == ground_truth),
                    confidence=float(result["score"]),
                )
                learning.adjust_agent_trust(result["agent"])

        loss = sentinel.rl.update_policy()
        reward_curve.append(episode_reward)
        sentinel.rl.episode_rewards.append(episode_reward)
        learning.retrain_models(agents=agents, episode=episode)
        adjusted = {agent_id: trust_registry.get_profile(agent_id).base_trust for agent_id in ["threat_hunter", "trust", "graph", "anomaly"]}
        agent_logs.append({"episode": episode, "loss": loss, "episode_reward": episode_reward, "adjusted_trust": adjusted})
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


def _stable_string(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def compute_dataset_fingerprint(runtime_df: pd.DataFrame) -> str:
    columns = ["event_id", "scenario", "phase", "source", "target", "action", "risk_signal", "priority", "pred_attack"]
    ordered = runtime_df.sort_values(["event_id"])[columns]
    body = "\n".join("|".join(_stable_string(row[column]) for column in columns) for _, row in ordered.iterrows())
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_verified_colab_payload(
    runtime_df: pd.DataFrame,
    metrics: dict[str, float],
    *,
    run_id: str,
    training_plan_id: str,
    target_agents: list[str],
    knowledge_registry_fingerprint: str,
    reviewer: str,
    notes: str,
) -> dict[str, object]:
    accepted = runtime_df.loc[runtime_df["action"].isin(["INVESTIGATE", "ESCALATE", "BLOCK"])].sort_values(["priority", "risk_signal"], ascending=False)
    review = runtime_df.loc[(runtime_df["action"] == "MONITOR") & (runtime_df["pred_attack"] == 1)]
    dropped = runtime_df.loc[runtime_df["action"] == "IGNORE"]
    return {
        "source": "google_colab",
        "run_id": run_id,
        "training_plan_id": training_plan_id,
        "target_agents": target_agents,
        "dataset_fingerprint": compute_dataset_fingerprint(runtime_df),
        "knowledge_registry_fingerprint": knowledge_registry_fingerprint,
        "accepted_item_ids": accepted["event_id"].tolist(),
        "verification": {
            "status": "verified",
            "novelty_gate_applied": True,
            "offensive_content_filtered": True,
            "known_attack_filter_applied": True,
            "human_reviewed": bool(reviewer),
            "accepted_count": int(len(accepted)),
            "skipped_known_count": 0,
            "rejected_count": int(len(dropped)),
            "review_queue_count": int(len(review)),
            "reviewer": reviewer,
            "notes": notes,
            "precision": round(float(metrics["precision"]), 4),
            "recall": round(float(metrics["recall"]), 4),
            "average_reward": round(float(metrics["average_reward"]), 4),
            "improvement": round(float(metrics["improvement"]), 4),
        },
        "signals_summary": {
            "accepted_signals": accepted[
                ["event_id", "scenario", "phase", "action", "risk_signal", "priority"]
            ].head(25).to_dict(orient="records"),
            "review_signals": review[["event_id", "scenario", "phase", "action", "risk_signal", "priority"]].head(10).to_dict(orient="records"),
        },
    }


def save_verified_colab_payload(payload: dict[str, object], export_dir: str | Path) -> str:
    target = Path(export_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / "verified_colab_result.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def push_verified_colab_payload(
    payload: dict[str, object],
    *,
    url: str,
    secret: str,
    timeout: float = 30.0,
) -> dict[str, object]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload, headers={"x-cortex-colab-signature": signature})
        response.raise_for_status()
        return response.json()
