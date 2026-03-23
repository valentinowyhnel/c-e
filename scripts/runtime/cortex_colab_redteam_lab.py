from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


RED_ACTIONS = [
    "scan",
    "access_resource",
    "escalate_privilege",
    "move_laterally",
    "stay_silent",
    "exfiltrate",
]
DEFENSE_ACTIONS = ["observe", "step_up_auth", "segment", "deceive", "contain"]
AGENT_NAMES = ["sentinel", "trust_engine", "threat_hunter", "graph_analyst", "anomaly_detector"]
ACTION_TO_IDX = {name: idx for idx, name in enumerate(RED_ACTIONS)}
ROLE_TO_IDX = {"user": 0, "device": 1, "service": 2, "resource": 3, "session": 4}
SCENARIOS = ["zero_day", "low_and_slow", "multi_step", "insider", "normal_noise"]


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def configure_gpu_runtime(device: torch.device) -> dict[str, object]:
    settings = {
        "device": str(device),
        "cuda_enabled": device.type == "cuda",
        "amp_enabled": device.type == "cuda",
        "tf32_enabled": False,
    }
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        if hasattr(torch.backends.cuda.matmul, "allow_tf32"):
            torch.backends.cuda.matmul.allow_tf32 = True
        if hasattr(torch.backends.cudnn, "allow_tf32"):
            torch.backends.cudnn.allow_tf32 = True
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("high")
        settings["tf32_enabled"] = True
    return settings


@dataclass
class EpisodeEvent:
    episode: int
    step: int
    scenario: str
    attacker_action: str
    defense_action: str
    source: str
    target: str
    privilege_level: int
    privilege_label: str
    visible_ratio: float
    detection_risk: float
    detection_signal: float
    attack_path_score: float
    target_value: float
    preposition_score: float
    low_and_slow_score: float
    zero_day_score: float
    fused_signal: float
    predicted_next_action: str
    prediction_confidence: float
    sentinel_score: float
    trust_engine_score: float
    threat_hunter_score: float
    graph_analyst_score: float
    anomaly_detector_score: float
    agent_vote_count: int
    token_ttl_minutes: int
    token_age_minutes: int
    token_remaining_minutes: int
    token_remaining_ratio: float
    token_expired: int
    attack_success: int
    detected_early: int
    blocked: int
    exfiltration_success: int


def privilege_label(privilege_level: int) -> str:
    return {
        0: "session_user",
        1: "delegated_access",
        2: "privileged_operator",
        3: "admin",
    }.get(privilege_level, "unknown")


def initialize_token_profile(scenario: str) -> tuple[int, int]:
    ttl_minutes = random.choice([20, 30, 45, 60, 120, 240])
    age_minutes = {
        "zero_day": random.randint(0, max(1, ttl_minutes // 5)),
        "low_and_slow": random.randint(ttl_minutes // 3, max(ttl_minutes // 3, int(ttl_minutes * 0.8))),
        "multi_step": random.randint(ttl_minutes // 6, max(ttl_minutes // 6, ttl_minutes // 2)),
        "insider": random.randint(ttl_minutes // 4, max(ttl_minutes // 4, int(ttl_minutes * 0.7))),
        "normal_noise": random.randint(0, max(1, ttl_minutes // 4)),
    }[scenario]
    return ttl_minutes, min(age_minutes, ttl_minutes)


def token_step_minutes(attacker_action: str, scenario: str) -> int:
    return {
        "scan": 3,
        "access_resource": 4,
        "escalate_privilege": 6,
        "move_laterally": 5,
        "stay_silent": 10 if scenario == "low_and_slow" else 7,
        "exfiltrate": 4,
    }[attacker_action]


def build_dynamic_environment(seed: int = 42) -> nx.Graph:
    rng = random.Random(seed)
    graph = nx.Graph()
    users = [f"user-{idx}" for idx in range(10)]
    devices = [f"device-{idx}" for idx in range(14)]
    services = [f"service-{idx}" for idx in range(8)]
    resources = [f"resource-{idx}" for idx in range(8)]
    sessions = [f"session-{idx}" for idx in range(12)]
    trust_zones = ["corp", "dmz", "prod", "lab"]

    for node in users:
        graph.add_node(
            node,
            role="user",
            crown_jewel=False,
            value=0.25 + 0.05 * rng.random(),
            trust_zone=rng.choice(["corp", "lab"]),
            tier=1,
            token_sensitivity=0.30 + 0.15 * rng.random(),
            blast_radius=0.20 + 0.10 * rng.random(),
            privilege_requirement=rng.choice([0, 1]),
        )
    for idx, node in enumerate(devices):
        graph.add_node(
            node,
            role="device",
            crown_jewel=idx in {7, 8, 10, 12},
            value=0.30 + 0.10 * rng.random(),
            trust_zone=trust_zones[idx % len(trust_zones)],
            tier=2,
            token_sensitivity=0.35 + 0.20 * rng.random(),
            blast_radius=0.25 + 0.20 * rng.random(),
            privilege_requirement=rng.choice([0, 1, 2]),
        )
    for idx, node in enumerate(services):
        graph.add_node(
            node,
            role="service",
            crown_jewel=idx in {3, 5, 6},
            value=0.45 + 0.15 * rng.random(),
            trust_zone=["prod", "dmz", "prod", "corp", "lab", "prod", "prod", "dmz"][idx],
            tier=3,
            token_sensitivity=0.45 + 0.20 * rng.random(),
            blast_radius=0.35 + 0.25 * rng.random(),
            privilege_requirement=rng.choice([1, 2, 3]),
        )
    for idx, node in enumerate(resources):
        graph.add_node(
            node,
            role="resource",
            crown_jewel=idx in {2, 4, 5, 6},
            value=0.60 + 0.18 * rng.random(),
            trust_zone=["prod", "prod", "prod", "corp", "dmz", "prod", "prod", "lab"][idx],
            tier=4,
            token_sensitivity=0.55 + 0.20 * rng.random(),
            blast_radius=0.50 + 0.25 * rng.random(),
            privilege_requirement=rng.choice([1, 2, 3]),
        )
    for node in sessions:
        graph.add_node(
            node,
            role="session",
            crown_jewel=False,
            value=0.15 + 0.04 * rng.random(),
            trust_zone=rng.choice(["corp", "lab", "dmz"]),
            tier=1,
            token_sensitivity=0.60 + 0.20 * rng.random(),
            blast_radius=0.10 + 0.08 * rng.random(),
            privilege_requirement=0,
        )

    for idx, user in enumerate(users):
        device = devices[idx % len(devices)]
        session = sessions[idx % len(sessions)]
        graph.add_edge(user, device, relation="uses")
        graph.add_edge(user, session, relation="authenticates")
        graph.add_edge(session, device, relation="binds")

    for idx, device in enumerate(devices):
        graph.add_edge(device, services[idx % len(services)], relation="reaches")
        graph.add_edge(device, services[(idx + 2) % len(services)], relation="reaches")
        graph.add_edge(device, services[(idx + 5) % len(services)], relation="fallback")

    for idx, service in enumerate(services):
        graph.add_edge(service, resources[idx % len(resources)], relation="reads")
        graph.add_edge(service, resources[(idx + 1) % len(resources)], relation="reads")
        graph.add_edge(service, resources[(idx + 3) % len(resources)], relation="writes")

    graph.add_edge("user-0", "resource-5", relation="admin_path")
    graph.add_edge("service-5", "resource-4", relation="backup")
    graph.add_edge("device-8", "resource-2", relation="analytics")
    graph.add_edge("device-7", "service-5", relation="ops")
    graph.add_edge("user-3", "service-6", relation="break_glass")
    graph.add_edge("device-10", "service-6", relation="shadow_admin")
    graph.add_edge("session-2", "resource-6", relation="stale_token_path")
    graph.add_edge("session-9", "device-12", relation="orphaned_session")
    return graph


def draw_environment(graph: nx.Graph) -> None:
    palette = {
        "user": "#1f77b4",
        "device": "#ff7f0e",
        "service": "#2ca02c",
        "resource": "#d62728",
        "session": "#9467bd",
    }
    pos = nx.spring_layout(graph, seed=42)
    colors = [palette[graph.nodes[node]["role"]] for node in graph.nodes()]
    sizes = [900 if graph.nodes[node].get("crown_jewel") else 500 for node in graph.nodes()]
    plt.figure(figsize=(13, 9))
    nx.draw_networkx(graph, pos=pos, node_color=colors, node_size=sizes, with_labels=True, font_size=8, edge_color="#bbbbbb")
    plt.title("Dynamic Cortex Enterprise Graph")
    plt.axis("off")


def build_graph_tensors(graph: nx.Graph) -> tuple[list[str], torch.Tensor, torch.Tensor, torch.Tensor]:
    nodes = list(graph.nodes())
    pagerank = nx.pagerank(graph)
    betweenness = nx.betweenness_centrality(graph)
    zone_to_idx = {"corp": 0, "dmz": 1, "prod": 2, "lab": 3}
    features = []
    labels = []
    for node in nodes:
        data = graph.nodes[node]
        role = data["role"]
        role_vector = [float(role == key) for key in ["user", "device", "service", "resource", "session"]]
        zone_vector = [0.0] * len(zone_to_idx)
        zone_vector[zone_to_idx.get(str(data.get("trust_zone", "corp")), 0)] = 1.0
        features.append(
            [
                graph.degree(node) / 12.0,
                pagerank[node],
                betweenness[node],
                float(data.get("crown_jewel", False)),
                float(data.get("value", 0.2)),
                float(data.get("tier", 1)) / 4.0,
                float(data.get("token_sensitivity", 0.3)),
                float(data.get("blast_radius", 0.2)),
                float(data.get("privilege_requirement", 0)) / 3.0,
            ]
            + role_vector
            + zone_vector
        )
        labels.append(int(data.get("crown_jewel", False) or data["role"] in {"service", "resource"} or data.get("blast_radius", 0.0) >= 0.55))
    adjacency = torch.zeros((len(nodes), len(nodes)), dtype=torch.float32)
    index = {node: idx for idx, node in enumerate(nodes)}
    for left, right in graph.edges():
        adjacency[index[left], index[right]] = 1.0
        adjacency[index[right], index[left]] = 1.0
    adjacency += torch.eye(len(nodes))
    degree = adjacency.sum(dim=1)
    degree_inv = torch.diag(torch.pow(degree, -0.5))
    normalized = degree_inv @ adjacency @ degree_inv
    return nodes, torch.tensor(features, dtype=torch.float32), normalized, torch.tensor(labels, dtype=torch.float32)


class GraphRiskGCN(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 64, dropout: float = 0.10):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.out = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = adj @ x
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = adj @ x
        embedding = F.relu(self.fc2(x))
        logits = self.out(embedding).squeeze(-1)
        return logits, embedding


def train_graph_risk_model(
    graph: nx.Graph,
    device: torch.device,
    epochs: int = 180,
    hidden_dim: int = 64,
    dropout: float = 0.10,
    lr: float = 0.008,
) -> tuple[GraphRiskGCN, dict[str, float], torch.Tensor]:
    nodes, features, adjacency, labels = build_graph_tensors(graph)
    model = GraphRiskGCN(features.shape[1], hidden_dim=hidden_dim, dropout=dropout).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    x = features.to(device)
    adj = adjacency.to(device)
    y = labels.to(device)
    for _ in range(epochs):
        optimizer.zero_grad()
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits, _ = model(x, adj)
            loss = loss_fn(logits, y)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
    model.eval()
    with torch.no_grad():
        logits, embedding = model(x, adj)
    scores = torch.sigmoid(logits).cpu().numpy()
    return model, {node: float(scores[idx]) for idx, node in enumerate(nodes)}, embedding.cpu()


class AttackForecaster(nn.Module):
    def __init__(self, action_count: int, context_dim: int, hidden_dim: int = 96, num_layers: int = 2, dropout: float = 0.15):
        super().__init__()
        self.embedding = nn.Embedding(action_count, 12)
        lstm_dropout = dropout if num_layers > 1 else 0.0
        self.lstm = nn.LSTM(12 + context_dim, hidden_dim, num_layers=num_layers, dropout=lstm_dropout, batch_first=True)
        self.head = nn.Linear(hidden_dim, action_count)

    def forward(self, action_seq: torch.Tensor, context_seq: torch.Tensor) -> torch.Tensor:
        embedded = self.embedding(action_seq)
        x = torch.cat([embedded, context_seq], dim=-1)
        _, (hidden, _) = self.lstm(x)
        return self.head(hidden[-1])


def encode_forecaster_context(
    privilege_level: int,
    visible_ratio: float,
    detection_risk: float,
    target_score: float,
    path_score: float,
    preposition_score: float,
    low_and_slow_score: float,
    zero_day_score: float,
) -> np.ndarray:
    return np.array(
        [
            privilege_level,
            visible_ratio,
            detection_risk,
            target_score,
            path_score,
            preposition_score,
            low_and_slow_score,
            zero_day_score,
        ],
        dtype=np.float32,
    )


def encode_context(graph: nx.Graph, current_node: str, privilege_level: int, visible_ratio: float, detection_risk: float, scenario: str, node_risk: dict[str, float]) -> np.ndarray:
    data = graph.nodes[current_node]
    role_vector = np.zeros(len(ROLE_TO_IDX), dtype=np.float32)
    role_vector[ROLE_TO_IDX[data["role"]]] = 1.0
    scenario_vector = np.zeros(len(SCENARIOS), dtype=np.float32)
    scenario_vector[SCENARIOS.index(scenario)] = 1.0
    base = np.array(
        [
            privilege_level / 3.0,
            visible_ratio,
            detection_risk,
            float(data.get("value", 0.2)),
            float(node_risk.get(current_node, 0.2)),
            float(data.get("crown_jewel", False)),
        ],
        dtype=np.float32,
    )
    return np.concatenate([base, role_vector, scenario_vector]).astype(np.float32)


def build_forecaster_dataset(events_df: pd.DataFrame, sequence_len: int = 5) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    sequences = []
    contexts = []
    labels = []
    for _, episode_df in events_df.groupby("episode"):
        actions = episode_df["attacker_action"].map(ACTION_TO_IDX).tolist()
        context_cols = ["privilege_level", "visible_ratio", "detection_risk", "target_value", "attack_path_score", "preposition_score", "low_and_slow_score", "zero_day_score"]
        context = episode_df[context_cols].to_numpy(dtype=np.float32)
        if len(actions) <= sequence_len:
            continue
        for idx in range(len(actions) - sequence_len):
            sequences.append(actions[idx : idx + sequence_len])
            contexts.append(context[idx : idx + sequence_len])
            labels.append(actions[idx + sequence_len])
    return (
        torch.tensor(np.array(sequences), dtype=torch.long),
        torch.tensor(np.array(contexts), dtype=torch.float32),
        torch.tensor(np.array(labels), dtype=torch.long),
    )


def train_attack_forecaster(
    events_df: pd.DataFrame,
    device: torch.device,
    epochs: int = 30,
    hidden_dim: int = 96,
    num_layers: int = 2,
    dropout: float = 0.15,
    batch_size: int = 128,
    lr: float = 0.0025,
) -> AttackForecaster | None:
    action_seq, context_seq, labels = build_forecaster_dataset(events_df)
    if action_seq.numel() == 0 or context_seq.numel() == 0 or labels.numel() == 0:
        return None
    model = AttackForecaster(len(RED_ACTIONS), context_seq.shape[-1], hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    dataset = TensorDataset(action_seq, context_seq, labels)
    effective_batch_size = min(batch_size, len(dataset))
    loader = DataLoader(dataset, batch_size=effective_batch_size, shuffle=True, drop_last=False)
    mkldnn_previous = torch.backends.mkldnn.enabled
    if device.type != "cuda":
        torch.backends.mkldnn.enabled = False
    try:
        for _ in range(epochs):
            for batch_actions, batch_context, batch_labels in loader:
                optimizer.zero_grad()
                with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                    logits = model(batch_actions.to(device), batch_context.to(device))
                    loss = F.cross_entropy(logits, batch_labels.to(device))
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
    finally:
        torch.backends.mkldnn.enabled = mkldnn_previous
    return model


def predict_next_action(model: AttackForecaster | None, history: list[str], contexts: list[np.ndarray], device: torch.device) -> tuple[str, float]:
    if model is None or len(history) < 5:
        return "scan", 0.20
    action_tensor = torch.tensor([[ACTION_TO_IDX[action] for action in history[-5:]]], dtype=torch.long, device=device)
    context_tensor = torch.tensor(np.array([contexts[-5:]], dtype=np.float32), dtype=torch.float32, device=device)
    mkldnn_previous = torch.backends.mkldnn.enabled
    if device.type != "cuda":
        torch.backends.mkldnn.enabled = False
    try:
        with torch.no_grad():
            logits = model(action_tensor, context_tensor)
            probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()
    finally:
        torch.backends.mkldnn.enabled = mkldnn_previous
    idx = int(np.argmax(probs))
    return RED_ACTIONS[idx], float(probs[idx])


class QLearningAgent:
    def __init__(self, actions: list[str], alpha: float = 0.20, gamma: float = 0.96, epsilon: float = 1.0, epsilon_decay: float = 0.992, epsilon_min: float = 0.05):
        self.actions = actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.q = defaultdict(lambda: np.zeros(len(actions), dtype=np.float32))

    def choose(self, state: tuple[int, ...]) -> int:
        if random.random() < self.epsilon:
            return random.randrange(len(self.actions))
        return int(np.argmax(self.q[state]))

    def update(self, state: tuple[int, ...], action: int, reward: float, next_state: tuple[int, ...], done: bool) -> None:
        target = reward if done else reward + self.gamma * float(np.max(self.q[next_state]))
        self.q[state][action] += self.alpha * (target - self.q[state][action])

    def decay(self) -> None:
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)


def discretize_state(privilege_level: int, visible_ratio: float, detection_risk: float, detection_signal: float, target_value: float, scenario: str) -> tuple[int, ...]:
    return (
        privilege_level,
        min(4, int(visible_ratio * 5)),
        min(4, int(detection_risk * 5)),
        min(4, int(detection_signal * 5)),
        min(4, int(target_value * 5)),
        SCENARIOS.index(scenario),
    )


def red_reward(attack_success: bool, detected: bool, blocked: bool, exfil_success: bool, target_value: float) -> float:
    reward = 0.25 * attack_success + 0.55 * exfil_success + 0.20 * target_value
    reward += 0.20 * (not detected)
    reward -= 0.65 * blocked
    reward -= 0.30 * detected
    return float(reward)


def defense_reward(detected_early: bool, blocked: bool, false_positive: bool, attack_success: bool, exfil_success: bool) -> float:
    reward = 0.85 * detected_early + 0.75 * blocked
    reward -= 0.30 * false_positive
    reward -= 0.60 * attack_success
    reward -= 0.80 * exfil_success
    return float(reward)


def cortex_agent_scores(
    graph: nx.Graph,
    current_node: str,
    privilege_level: int,
    visible_ratio: float,
    detection_risk: float,
    scenario: str,
    node_risk: dict[str, float],
    predicted_next_action: str,
    token_remaining_ratio: float,
    token_expired: bool,
    token_ttl_minutes: int,
) -> dict[str, float]:
    data = graph.nodes[current_node]
    base_risk = node_risk[current_node]
    crown = float(data.get("crown_jewel", False))
    token_drift = 1.0 - token_remaining_ratio
    long_lived = float(token_ttl_minutes >= 120)
    blast_radius = float(data.get("blast_radius", 0.2))
    token_sensitivity = float(data.get("token_sensitivity", 0.3))
    privilege_requirement = float(data.get("privilege_requirement", 0)) / 3.0
    sentinel = min(
        1.0,
        0.26 * detection_risk
        + 0.15 * privilege_level / 3.0
        + 0.16 * base_risk
        + 0.16 * crown
        + 0.10 * float(token_expired)
        + 0.09 * blast_radius
        + 0.08 * token_sensitivity,
    )
    trust_engine = min(
        1.0,
        0.24 * privilege_level / 3.0
        + 0.12 * (1.0 - min(1.0, data.get("value", 0.3)))
        + 0.22 * float(scenario in {"insider", "zero_day"})
        + 0.18 * token_drift
        + 0.10 * long_lived,
        + 0.08 * privilege_requirement
        + 0.06 * token_sensitivity,
    )
    threat_hunter = min(
        1.0,
        0.24 * detection_risk
        + 0.22 * float(predicted_next_action in {"escalate_privilege", "exfiltrate"})
        + 0.16 * crown
        + 0.18 * float(scenario in {"low_and_slow", "zero_day"})
        + 0.10 * blast_radius
        + 0.10 * float(token_expired),
    )
    graph_analyst = min(1.0, 0.34 * base_risk + 0.24 * visible_ratio + 0.16 * crown + 0.16 * blast_radius + 0.10 * privilege_requirement)
    anomaly_detector = min(
        1.0,
        0.34 * detection_risk
        + 0.16 * float(scenario in {"zero_day", "low_and_slow"})
        + 0.10 * visible_ratio
        + 0.16 * token_drift
        + 0.14 * token_sensitivity
        + 0.10 * float(token_expired),
    )
    return {
        "sentinel": float(sentinel),
        "trust_engine": float(trust_engine),
        "threat_hunter": float(threat_hunter),
        "graph_analyst": float(graph_analyst),
        "anomaly_detector": float(anomaly_detector),
    }


def fuse_scores(agent_scores: dict[str, float]) -> tuple[float, dict[str, float]]:
    weights = {
        "sentinel": 0.25,
        "trust_engine": 0.20,
        "threat_hunter": 0.20,
        "graph_analyst": 0.15,
        "anomaly_detector": 0.20,
    }
    fused = sum(agent_scores[name] * weights[name] for name in weights)
    votes = {name: float(score >= 0.62) for name, score in agent_scores.items()}
    return float(fused), votes


def target_value(graph: nx.Graph, node: str) -> float:
    data = graph.nodes[node]
    return float(
        min(
            1.0,
            data["value"]
            + 0.18 * data.get("crown_jewel", False)
            + 0.14 * float(data.get("blast_radius", 0.2))
            + 0.08 * float(data.get("tier", 1)) / 4.0,
        )
    )


def attack_path_score(graph: nx.Graph, current: str) -> float:
    crown_nodes = [node for node, data in graph.nodes(data=True) if data.get("crown_jewel")]
    distances = []
    for node in crown_nodes:
        try:
            distances.append(nx.shortest_path_length(graph, current, node))
        except nx.NetworkXNoPath:
            continue
    if not distances:
        return 0.0
    return float(1.0 / (1.0 + min(distances)))


def choose_target(graph: nx.Graph, current: str, visible_nodes: set[str], action_name: str) -> str:
    neighbors = list(graph.neighbors(current))
    if action_name == "scan":
        options = list(set(neighbors + list(visible_nodes)))
    elif action_name == "move_laterally":
        options = neighbors or list(visible_nodes)
    elif action_name == "exfiltrate":
        options = [node for node in visible_nodes if graph.nodes[node]["role"] in {"resource", "service"}] or list(visible_nodes)
    else:
        options = list(visible_nodes)
    return random.choice(options or [current])


def step_environment(
    graph: nx.Graph,
    current: str,
    visible_nodes: set[str],
    privilege_level: int,
    detection_risk: float,
    scenario: str,
    attacker_action: str,
    defense_action: str,
    token_age_minutes: int,
    token_ttl_minutes: int,
) -> dict[str, object]:
    target = choose_target(graph, current, visible_nodes, attacker_action)
    target_data = graph.nodes[target]
    visible_nodes = set(visible_nodes)
    if attacker_action == "scan":
        visible_nodes.update(graph.neighbors(current))
    visible_ratio = min(1.0, len(visible_nodes) / graph.number_of_nodes())
    scenario_zero_day = 0.95 if scenario == "zero_day" else 0.15
    scenario_low_slow = 0.95 if scenario == "low_and_slow" else 0.15
    target_score = target_value(graph, target)
    path_score = attack_path_score(graph, current)
    privilege_requirement = int(target_data.get("privilege_requirement", 0))
    token_sensitivity = float(target_data.get("token_sensitivity", 0.3))
    blast_radius = float(target_data.get("blast_radius", 0.2))
    base_success = {
        "scan": 0.95,
        "access_resource": 0.44 + 0.10 * privilege_level - 0.06 * max(0, privilege_requirement - privilege_level) + 0.05 * (1.0 - token_sensitivity),
        "escalate_privilege": 0.22 + 0.12 * privilege_level + 0.15 * (scenario == "zero_day") + 0.08 * (blast_radius >= 0.55),
        "move_laterally": 0.45 + 0.10 * visible_ratio + 0.10 * (scenario == "low_and_slow"),
        "stay_silent": 0.90,
        "exfiltrate": 0.12 + 0.15 * privilege_level + 0.28 * target_score + 0.08 * blast_radius - 0.08 * token_sensitivity,
    }[attacker_action]
    defense_modifier = {
        "observe": 0.00,
        "step_up_auth": -0.10,
        "segment": -0.12,
        "deceive": -0.08,
        "contain": -0.22,
    }[defense_action]
    attack_success = random.random() < max(0.02, min(0.98, base_success + defense_modifier))
    blocked = defense_action == "contain" and detection_risk >= 0.52 and attacker_action in {"move_laterally", "exfiltrate", "escalate_privilege"}
    if blocked:
        attack_success = False

    if attack_success and attacker_action == "move_laterally":
        current = target
    if attack_success and attacker_action == "escalate_privilege":
        privilege_level = min(3, privilege_level + 1)
    if attack_success and attacker_action == "access_resource":
        current = target

    token_age_minutes = min(token_ttl_minutes + 30, token_age_minutes + token_step_minutes(attacker_action, scenario))
    if defense_action == "step_up_auth":
        token_age_minutes = min(token_ttl_minutes + 30, token_age_minutes + 3)
    if attack_success and attacker_action == "access_resource" and privilege_level >= 1:
        token_age_minutes = max(0, token_age_minutes - 8)

    risk_delta = {
        "scan": 0.12,
        "access_resource": 0.12 + 0.06 * token_sensitivity,
        "escalate_privilege": 0.20 + 0.06 * blast_radius,
        "move_laterally": 0.16 + 0.04 * blast_radius,
        "stay_silent": -0.08 if scenario == "low_and_slow" else -0.05,
        "exfiltrate": 0.24 + 0.10 * blast_radius,
    }[attacker_action]
    defense_risk_delta = {
        "observe": 0.03,
        "step_up_auth": 0.08,
        "segment": 0.10,
        "deceive": 0.06,
        "contain": 0.16,
    }[defense_action]
    detection_risk = float(np.clip(detection_risk + risk_delta + defense_risk_delta, 0.0, 1.0))
    if blocked:
        detection_risk = min(1.0, detection_risk + 0.12)

    token_expired = token_age_minutes >= token_ttl_minutes
    token_remaining_minutes = max(0, token_ttl_minutes - token_age_minutes)
    token_remaining_ratio = float(np.clip(token_remaining_minutes / max(1, token_ttl_minutes), 0.0, 1.0))

    detection_signal = float(
        np.clip(
            0.29 * detection_risk
            + 0.14 * privilege_level / 3.0
            + 0.10 * path_score
            + 0.15 * scenario_zero_day
            + 0.10 * scenario_low_slow
            + 0.15 * target_score
            + 0.10 * (1.0 - token_remaining_ratio)
            + 0.07 * float(token_ttl_minutes >= 120)
            + 0.10 * float(token_expired and privilege_level >= 1),
            0.0,
            1.0,
        )
    )
    exfiltration_success = int(attack_success and attacker_action == "exfiltrate" and privilege_level >= 2 and target_score >= 0.55)
    detected_early = int(detection_signal >= 0.62 and attacker_action in {"scan", "move_laterally", "escalate_privilege"})
    preposition_score = float(np.clip(0.45 * visible_ratio + 0.25 * path_score + 0.30 * privilege_level / 3.0, 0.0, 1.0))
    return {
        "current": current,
        "target": target,
        "visible_nodes": visible_nodes,
        "visible_ratio": visible_ratio,
        "privilege_level": privilege_level,
        "privilege_label": privilege_label(privilege_level),
        "detection_risk": detection_risk,
        "detection_signal": detection_signal,
        "token_ttl_minutes": token_ttl_minutes,
        "token_age_minutes": token_age_minutes,
        "token_remaining_minutes": token_remaining_minutes,
        "token_remaining_ratio": token_remaining_ratio,
        "token_expired": int(token_expired),
        "attack_success": int(attack_success),
        "detected_early": detected_early,
        "blocked": int(blocked),
        "exfiltration_success": exfiltration_success,
        "attack_path_score": path_score,
        "target_value": target_score,
        "preposition_score": preposition_score,
        "low_and_slow_score": scenario_low_slow,
        "zero_day_score": scenario_zero_day,
    }


def bootstrap_sequences(graph: nx.Graph, node_risk: dict[str, float], episodes: int = 60, steps_per_episode: int = 18) -> pd.DataFrame:
    rows = []
    for episode in range(episodes):
        scenario = SCENARIOS[episode % len(SCENARIOS)]
        current = random.choice([node for node, data in graph.nodes(data=True) if data["role"] in {"device", "user"}])
        visible_nodes = {current}
        privilege_level = 0
        detection_risk = 0.10
        token_ttl_minutes, token_age_minutes = initialize_token_profile(scenario)
        history: list[str] = []
        contexts: list[np.ndarray] = []
        for step in range(steps_per_episode):
            if scenario == "low_and_slow":
                action = random.choices(RED_ACTIONS, weights=[0.30, 0.12, 0.10, 0.12, 0.26, 0.10])[0]
            elif scenario == "zero_day":
                action = random.choices(RED_ACTIONS, weights=[0.18, 0.15, 0.24, 0.14, 0.10, 0.19])[0]
            else:
                action = random.choices(RED_ACTIONS, weights=[0.20, 0.20, 0.16, 0.18, 0.08, 0.18])[0]
            result = step_environment(graph, current, visible_nodes, privilege_level, detection_risk, scenario, action, "observe", token_age_minutes, token_ttl_minutes)
            current = str(result["current"])
            visible_nodes = set(result["visible_nodes"])
            privilege_level = int(result["privilege_level"])
            detection_risk = float(result["detection_risk"])
            token_age_minutes = int(result["token_age_minutes"])
            token_ttl_minutes = int(result["token_ttl_minutes"])
            rows.append(
                {
                    "episode": episode,
                    "step": step,
                    "scenario": scenario,
                    "attacker_action": action,
                    "privilege_level": privilege_level,
                    "privilege_label": result["privilege_label"],
                    "visible_ratio": result["visible_ratio"],
                    "detection_risk": detection_risk,
                    "target_value": result["target_value"],
                    "attack_path_score": result["attack_path_score"],
                    "preposition_score": result["preposition_score"],
                    "low_and_slow_score": result["low_and_slow_score"],
                    "zero_day_score": result["zero_day_score"],
                    "token_ttl_minutes": token_ttl_minutes,
                    "token_age_minutes": token_age_minutes,
                    "token_remaining_minutes": result["token_remaining_minutes"],
                    "token_remaining_ratio": result["token_remaining_ratio"],
                    "token_expired": result["token_expired"],
                }
            )
            history.append(action)
            contexts.append(
                encode_forecaster_context(
                    privilege_level=privilege_level,
                    visible_ratio=float(result["visible_ratio"]),
                    detection_risk=detection_risk,
                    target_score=float(result["target_value"]),
                    path_score=float(result["attack_path_score"]),
                    preposition_score=float(result["preposition_score"]),
                    low_and_slow_score=float(result["low_and_slow_score"]),
                    zero_day_score=float(result["zero_day_score"]),
                )
            )
    return pd.DataFrame(rows)


def train_dual_rl(
    graph: nx.Graph,
    node_risk: dict[str, float],
    forecaster: AttackForecaster | None,
    device: torch.device,
    episodes: int = 80,
    steps_per_episode: int = 20,
    attacker: QLearningAgent | None = None,
    defender: QLearningAgent | None = None,
) -> tuple[QLearningAgent, QLearningAgent, pd.DataFrame, pd.DataFrame]:
    attacker = attacker or QLearningAgent(RED_ACTIONS, epsilon_decay=0.985)
    defender = defender or QLearningAgent(DEFENSE_ACTIONS, epsilon_decay=0.986)
    events: list[dict[str, object]] = []
    episode_stats = []
    viable_starts = [node for node, data in graph.nodes(data=True) if data["role"] in {"user", "device"}]

    for episode in range(episodes):
        scenario = SCENARIOS[episode % len(SCENARIOS)]
        current = random.choice(viable_starts)
        visible_nodes = {current}
        privilege_level = 0
        detection_risk = 0.10 if scenario != "zero_day" else 0.16
        token_ttl_minutes, token_age_minutes = initialize_token_profile(scenario)
        action_history: list[str] = []
        context_history: list[np.ndarray] = []
        total_red = 0.0
        total_blue = 0.0
        early_detections = 0
        exfiltration_count = 0
        attacks_succeeded = 0

        for step in range(steps_per_episode):
            current_target_value = target_value(graph, current)
            attacker_state = discretize_state(privilege_level, len(visible_nodes) / graph.number_of_nodes(), detection_risk, detection_risk, current_target_value, scenario)
            defender_state = discretize_state(privilege_level, len(visible_nodes) / graph.number_of_nodes(), detection_risk, detection_risk, current_target_value, scenario)
            attacker_action_idx = attacker.choose(attacker_state)
            defender_action_idx = defender.choose(defender_state)
            attacker_action = RED_ACTIONS[attacker_action_idx]
            defender_action = DEFENSE_ACTIONS[defender_action_idx]

            predicted_next_action, prediction_confidence = predict_next_action(forecaster, action_history, context_history, device)
            pre_step_remaining_ratio = float(np.clip(max(0, token_ttl_minutes - token_age_minutes) / max(1, token_ttl_minutes), 0.0, 1.0))
            pre_step_expired = token_age_minutes >= token_ttl_minutes
            agent_score_map = cortex_agent_scores(
                graph,
                current,
                privilege_level,
                len(visible_nodes) / graph.number_of_nodes(),
                detection_risk,
                scenario,
                node_risk,
                predicted_next_action,
                pre_step_remaining_ratio,
                pre_step_expired,
                token_ttl_minutes,
            )
            fused_signal, agent_votes = fuse_scores(agent_score_map)

            result = step_environment(
                graph,
                current,
                visible_nodes,
                privilege_level,
                detection_risk,
                scenario,
                attacker_action,
                defender_action,
                token_age_minutes,
                token_ttl_minutes,
            )
            current = str(result["current"])
            visible_nodes = set(result["visible_nodes"])
            privilege_level = int(result["privilege_level"])
            detection_risk = float(result["detection_risk"])
            token_age_minutes = int(result["token_age_minutes"])
            token_ttl_minutes = int(result["token_ttl_minutes"])
            attacks_succeeded += int(result["attack_success"])
            early_detections += int(result["detected_early"])
            exfiltration_count += int(result["exfiltration_success"])

            false_positive = bool(defender_action in {"segment", "contain"} and not result["attack_success"] and attacker_action == "stay_silent")
            red_r = red_reward(bool(result["attack_success"]), bool(result["detected_early"]), bool(result["blocked"]), bool(result["exfiltration_success"]), float(result["target_value"]))
            blue_r = defense_reward(bool(result["detected_early"]), bool(result["blocked"]), false_positive, bool(result["attack_success"]), bool(result["exfiltration_success"]))
            total_red += red_r
            total_blue += blue_r

            next_target_value = target_value(graph, current)
            next_state = discretize_state(privilege_level, len(visible_nodes) / graph.number_of_nodes(), detection_risk, float(result["detection_signal"]), next_target_value, scenario)
            done = step == steps_per_episode - 1 or result["exfiltration_success"] == 1
            attacker.update(attacker_state, attacker_action_idx, red_r, next_state, done)
            defender.update(defender_state, defender_action_idx, blue_r, next_state, done)

            context = encode_forecaster_context(
                privilege_level=privilege_level,
                visible_ratio=float(result["visible_ratio"]),
                detection_risk=detection_risk,
                target_score=float(result["target_value"]),
                path_score=float(result["attack_path_score"]),
                preposition_score=float(result["preposition_score"]),
                low_and_slow_score=float(result["low_and_slow_score"]),
                zero_day_score=float(result["zero_day_score"]),
            )
            action_history.append(attacker_action)
            context_history.append(context)

            event = EpisodeEvent(
                episode=episode,
                step=step,
                scenario=scenario,
                attacker_action=attacker_action,
                defense_action=defender_action,
                source=current,
                target=str(result["target"]),
                privilege_level=privilege_level,
                privilege_label=str(result["privilege_label"]),
                visible_ratio=float(result["visible_ratio"]),
                detection_risk=detection_risk,
                detection_signal=float(result["detection_signal"]),
                attack_path_score=float(result["attack_path_score"]),
                target_value=float(result["target_value"]),
                preposition_score=float(result["preposition_score"]),
                low_and_slow_score=float(result["low_and_slow_score"]),
                zero_day_score=float(result["zero_day_score"]),
                fused_signal=float(fused_signal),
                predicted_next_action=predicted_next_action,
                prediction_confidence=prediction_confidence,
                sentinel_score=float(agent_score_map["sentinel"]),
                trust_engine_score=float(agent_score_map["trust_engine"]),
                threat_hunter_score=float(agent_score_map["threat_hunter"]),
                graph_analyst_score=float(agent_score_map["graph_analyst"]),
                anomaly_detector_score=float(agent_score_map["anomaly_detector"]),
                agent_vote_count=int(sum(agent_votes.values())),
                token_ttl_minutes=int(result["token_ttl_minutes"]),
                token_age_minutes=int(result["token_age_minutes"]),
                token_remaining_minutes=int(result["token_remaining_minutes"]),
                token_remaining_ratio=float(result["token_remaining_ratio"]),
                token_expired=int(result["token_expired"]),
                attack_success=int(result["attack_success"]),
                detected_early=int(result["detected_early"]),
                blocked=int(result["blocked"]),
                exfiltration_success=int(result["exfiltration_success"]),
            )
            events.append(asdict(event))
            if done:
                break

        attacker.decay()
        defender.decay()
        episode_stats.append(
            {
                "episode": episode,
                "scenario": scenario,
                "red_reward": total_red,
                "blue_reward": total_blue,
                "attacks_succeeded": attacks_succeeded,
                "early_detections": early_detections,
                "exfiltration_count": exfiltration_count,
            }
        )
    return attacker, defender, pd.DataFrame(events), pd.DataFrame(episode_stats)


def evaluate_simulation(events_df: pd.DataFrame) -> dict[str, object]:
    pred_attack = (events_df["fused_signal"] >= 0.58).astype(int)
    y_true = events_df["attack_success"].astype(int)
    pred_zero = (events_df["predicted_next_action"].isin(["escalate_privilege", "exfiltrate"])).astype(int)
    true_zero = (events_df["zero_day_score"] >= 0.75).astype(int)
    shifted = events_df.groupby("episode")["attacker_action"].shift(-1).fillna("scan")
    grouped = events_df.groupby("episode").agg(
        reaction_step=("detected_early", lambda s: int(np.argmax(s.to_numpy() > 0)) if s.sum() else len(s)),
        attack_success=("attack_success", "sum"),
        blocked=("blocked", "sum"),
        exfiltration_success=("exfiltration_success", "sum"),
    )
    return {
        "anticipation_precision": precision_score(y_true, pred_attack, zero_division=0),
        "anticipation_recall": recall_score(y_true, pred_attack, zero_division=0),
        "anticipation_f1": f1_score(y_true, pred_attack, zero_division=0),
        "next_action_accuracy": accuracy_score(shifted, events_df["predicted_next_action"]),
        "zero_day_proxy_precision": precision_score(true_zero, pred_zero, zero_division=0),
        "zero_day_proxy_recall": recall_score(true_zero, pred_zero, zero_division=0),
        "early_detection_rate": float(events_df["detected_early"].mean()),
        "low_and_slow_detection_rate": float(events_df.loc[events_df["scenario"] == "low_and_slow", "detected_early"].mean()),
        "mean_reaction_step": float(grouped["reaction_step"].mean()),
        "attack_success_rate": float(events_df["attack_success"].mean()),
        "defense_block_rate": float(events_df["blocked"].mean()),
        "exfiltration_success_rate": float(events_df["exfiltration_success"].mean()),
        "critical_signal_rate": float((events_df["fused_signal"] >= 0.70).mean()),
        "anticipated_events": int(events_df["detected_early"].sum()),
        "expired_token_event_rate": float(events_df["token_expired"].mean()),
        "mean_token_age_minutes": float(events_df["token_age_minutes"].mean()),
        "mean_token_remaining_ratio": float(events_df["token_remaining_ratio"].mean()),
        "admin_path_event_rate": float((events_df["privilege_level"] >= 3).mean()),
    }


def build_signal_table(events_df: pd.DataFrame) -> pd.DataFrame:
    table = events_df.copy()
    table["signal_priority"] = np.where(table["fused_signal"] >= 0.72, "critical", np.where(table["fused_signal"] >= 0.58, "high", "review"))
    table["token_pressure"] = np.clip((1.0 - table["token_remaining_ratio"]) * (1.0 + 0.20 * table["privilege_level"]), 0.0, 1.0)
    table["agent_consensus"] = np.where(table["agent_vote_count"] >= 4, "strong", np.where(table["agent_vote_count"] >= 2, "medium", "weak"))
    table["recommended_cortex_route"] = np.select(
        [
            table["fused_signal"] >= 0.75,
            (table["token_expired"] == 1) | ((table["token_remaining_ratio"] <= 0.20) & (table["privilege_level"] >= 2)),
            table["preposition_score"] >= 0.62,
            table["predicted_next_action"].isin(["escalate_privilege", "exfiltrate"]),
        ],
        ["sentinel", "trust_engine", "graph_analyst", "threat_hunter"],
        default="trust_engine",
    )
    return table


def build_graph_inventory(graph: nx.Graph, node_risk: dict[str, float]) -> pd.DataFrame:
    rows = []
    pagerank = nx.pagerank(graph)
    for node, data in graph.nodes(data=True):
        rows.append(
            {
                "node": node,
                "role": data["role"],
                "trust_zone": data.get("trust_zone", "corp"),
                "tier": int(data.get("tier", 1)),
                "value": float(data.get("value", 0.2)),
                "crown_jewel": int(data.get("crown_jewel", False)),
                "token_sensitivity": float(data.get("token_sensitivity", 0.3)),
                "blast_radius": float(data.get("blast_radius", 0.2)),
                "privilege_requirement": int(data.get("privilege_requirement", 0)),
                "degree": int(graph.degree(node)),
                "pagerank": float(pagerank[node]),
                "node_risk": float(node_risk.get(node, 0.0)),
            }
        )
    return pd.DataFrame(rows).sort_values(["node_risk", "blast_radius", "value"], ascending=[False, False, False]).reset_index(drop=True)


def analyze_training_results(signals_df: pd.DataFrame, episode_df: pd.DataFrame, graph_inventory_df: pd.DataFrame, loop_metrics_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    risky_entities_df = (
        signals_df.groupby(["target", "scenario"])
        .agg(
            event_count=("target", "size"),
            mean_fused_signal=("fused_signal", "mean"),
            early_detection_rate=("detected_early", "mean"),
            block_rate=("blocked", "mean"),
            exfiltration_rate=("exfiltration_success", "mean"),
            max_privilege=("privilege_level", "max"),
            mean_token_pressure=("token_pressure", "mean"),
        )
        .reset_index()
        .sort_values(["mean_fused_signal", "exfiltration_rate", "max_privilege"], ascending=[False, False, False])
    )

    analysis_rows = [
        {
            "analysis_view": "agent_mean_scores",
            "dimension": "sentinel",
            "value": float(signals_df["sentinel_score"].mean()),
        },
        {
            "analysis_view": "agent_mean_scores",
            "dimension": "trust_engine",
            "value": float(signals_df["trust_engine_score"].mean()),
        },
        {
            "analysis_view": "agent_mean_scores",
            "dimension": "threat_hunter",
            "value": float(signals_df["threat_hunter_score"].mean()),
        },
        {
            "analysis_view": "agent_mean_scores",
            "dimension": "graph_analyst",
            "value": float(signals_df["graph_analyst_score"].mean()),
        },
        {
            "analysis_view": "agent_mean_scores",
            "dimension": "anomaly_detector",
            "value": float(signals_df["anomaly_detector_score"].mean()),
        },
        {
            "analysis_view": "loop_summary",
            "dimension": "mean_blue_reward",
            "value": float(episode_df["blue_reward"].mean()),
        },
        {
            "analysis_view": "loop_summary",
            "dimension": "mean_red_reward",
            "value": float(episode_df["red_reward"].mean()),
        },
        {
            "analysis_view": "token_summary",
            "dimension": "expired_token_rate",
            "value": float(signals_df["token_expired"].mean()),
        },
        {
            "analysis_view": "token_summary",
            "dimension": "mean_token_pressure",
            "value": float(signals_df["token_pressure"].mean()),
        },
        {
            "analysis_view": "graph_summary",
            "dimension": "high_risk_nodes",
            "value": float((graph_inventory_df["node_risk"] >= 0.70).sum()),
        },
        {
            "analysis_view": "metrics_history",
            "dimension": "best_anticipation_f1",
            "value": float(loop_metrics_df["anticipation_f1"].max()),
        },
    ]
    return pd.DataFrame(analysis_rows), risky_entities_df


def defense_objective(metrics: dict[str, object] | pd.Series) -> float:
    get = metrics.get if hasattr(metrics, "get") else lambda key, default=0.0: default
    return float(
        0.28 * float(get("anticipation_f1", 0.0))
        + 0.18 * float(get("early_detection_rate", 0.0))
        + 0.18 * float(get("defense_block_rate", 0.0))
        + 0.12 * float(get("critical_signal_rate", 0.0))
        + 0.10 * float(get("next_action_accuracy", 0.0))
        - 0.18 * float(get("exfiltration_success_rate", 0.0))
        - 0.10 * float(get("attack_success_rate", 0.0))
    )


def run_agent_training_loops(
    device: torch.device,
    loops: int = 3,
    seed: int = 42,
    bootstrap_episodes: int = 70,
    bootstrap_steps: int = 18,
    forecaster_epochs: int = 35,
    rl_episodes: int = 90,
    rl_steps: int = 22,
    graph_epochs: int = 180,
    graph_hidden_dim: int = 64,
    forecaster_hidden_dim: int = 96,
    forecaster_layers: int = 2,
    forecaster_batch_size: int = 128,
) -> dict[str, object]:
    gpu_runtime = configure_gpu_runtime(device)
    combined_bootstrap = []
    combined_events = []
    combined_episode = []
    loop_metrics = []
    attacker: QLearningAgent | None = None
    defender: QLearningAgent | None = None
    latest_graph = None
    latest_graph_model = None
    latest_node_risk = None
    latest_node_embeddings = None
    latest_forecaster = None

    for loop_idx in range(loops):
        loop_seed = seed + loop_idx
        set_seed(loop_seed)
        graph = build_dynamic_environment(seed=loop_seed)
        graph_model, node_risk, node_embeddings = train_graph_risk_model(
            graph,
            device=device,
            epochs=graph_epochs,
            hidden_dim=graph_hidden_dim,
        )
        bootstrap_df = bootstrap_sequences(graph, node_risk, episodes=bootstrap_episodes, steps_per_episode=bootstrap_steps).copy()
        bootstrap_df["training_loop"] = loop_idx
        combined_bootstrap.append(bootstrap_df)
        bootstrap_corpus = pd.concat(combined_bootstrap, ignore_index=True)
        forecaster = train_attack_forecaster(
            bootstrap_corpus,
            device=device,
            epochs=forecaster_epochs,
            hidden_dim=forecaster_hidden_dim,
            num_layers=forecaster_layers,
            batch_size=forecaster_batch_size,
        )
        attacker, defender, events_df, episode_df = train_dual_rl(
            graph=graph,
            node_risk=node_risk,
            forecaster=forecaster,
            device=device,
            episodes=rl_episodes,
            steps_per_episode=rl_steps,
            attacker=attacker,
            defender=defender,
        )
        events_df = events_df.copy()
        episode_df = episode_df.copy()
        events_df["training_loop"] = loop_idx
        episode_df["training_loop"] = loop_idx
        signals_df = build_signal_table(events_df)
        metrics = evaluate_simulation(events_df)
        metrics["training_loop"] = loop_idx
        metrics["node_count"] = graph.number_of_nodes()
        metrics["edge_count"] = graph.number_of_edges()
        metrics["graph_epochs"] = graph_epochs
        metrics["graph_hidden_dim"] = graph_hidden_dim
        metrics["forecaster_hidden_dim"] = forecaster_hidden_dim
        metrics["forecaster_layers"] = forecaster_layers
        metrics["forecaster_batch_size"] = forecaster_batch_size
        loop_metrics.append(metrics)
        combined_events.append(signals_df)
        combined_episode.append(episode_df)
        latest_graph = graph
        latest_graph_model = graph_model
        latest_node_risk = node_risk
        latest_node_embeddings = node_embeddings
        latest_forecaster = forecaster

    bootstrap_df = pd.concat(combined_bootstrap, ignore_index=True)
    signals_df = pd.concat(combined_events, ignore_index=True)
    episode_df = pd.concat(combined_episode, ignore_index=True)
    loop_metrics_df = pd.DataFrame(loop_metrics)
    graph_inventory_df = build_graph_inventory(latest_graph, latest_node_risk)
    analysis_df, risky_entities_df = analyze_training_results(signals_df, episode_df, graph_inventory_df, loop_metrics_df)
    loop_metrics_df = loop_metrics_df.copy()
    loop_metrics_df["defense_objective"] = loop_metrics_df.apply(defense_objective, axis=1)
    return {
        "graph": latest_graph,
        "graph_model": latest_graph_model,
        "node_risk": latest_node_risk,
        "node_embeddings": latest_node_embeddings,
        "forecaster": latest_forecaster,
        "attacker": attacker,
        "defender": defender,
        "bootstrap_df": bootstrap_df,
        "signals_df": signals_df,
        "events_df": signals_df.copy(),
        "episode_df": episode_df,
        "loop_metrics_df": loop_metrics_df,
        "graph_inventory_df": graph_inventory_df,
        "analysis_df": analysis_df,
        "risky_entities_df": risky_entities_df,
        "gpu_runtime": gpu_runtime,
    }


def optimize_agent_training(
    device: torch.device,
    search_plan: list[dict[str, int]] | None = None,
    seed: int = 42,
) -> dict[str, object]:
    if search_plan is None:
        if device.type == "cuda":
            search_plan = [
                {
                    "loops": 4,
                    "bootstrap_episodes": 90,
                    "bootstrap_steps": 20,
                    "forecaster_epochs": 42,
                    "rl_episodes": 120,
                    "rl_steps": 24,
                    "graph_epochs": 220,
                    "graph_hidden_dim": 96,
                    "forecaster_hidden_dim": 128,
                    "forecaster_layers": 2,
                    "forecaster_batch_size": 256,
                },
                {
                    "loops": 5,
                    "bootstrap_episodes": 110,
                    "bootstrap_steps": 22,
                    "forecaster_epochs": 54,
                    "rl_episodes": 140,
                    "rl_steps": 26,
                    "graph_epochs": 260,
                    "graph_hidden_dim": 128,
                    "forecaster_hidden_dim": 160,
                    "forecaster_layers": 3,
                    "forecaster_batch_size": 384,
                },
                {
                    "loops": 6,
                    "bootstrap_episodes": 130,
                    "bootstrap_steps": 24,
                    "forecaster_epochs": 64,
                    "rl_episodes": 160,
                    "rl_steps": 28,
                    "graph_epochs": 300,
                    "graph_hidden_dim": 160,
                    "forecaster_hidden_dim": 192,
                    "forecaster_layers": 3,
                    "forecaster_batch_size": 512,
                },
            ]
        else:
            search_plan = [
                {
                    "loops": 3,
                    "bootstrap_episodes": 60,
                    "bootstrap_steps": 16,
                    "forecaster_epochs": 28,
                    "rl_episodes": 70,
                    "rl_steps": 20,
                    "graph_epochs": 180,
                    "graph_hidden_dim": 64,
                    "forecaster_hidden_dim": 96,
                    "forecaster_layers": 2,
                    "forecaster_batch_size": 128,
                },
                {
                    "loops": 4,
                    "bootstrap_episodes": 70,
                    "bootstrap_steps": 18,
                    "forecaster_epochs": 35,
                    "rl_episodes": 90,
                    "rl_steps": 22,
                    "graph_epochs": 220,
                    "graph_hidden_dim": 96,
                    "forecaster_hidden_dim": 128,
                    "forecaster_layers": 2,
                    "forecaster_batch_size": 192,
                },
                {
                    "loops": 5,
                    "bootstrap_episodes": 80,
                    "bootstrap_steps": 20,
                    "forecaster_epochs": 40,
                    "rl_episodes": 100,
                    "rl_steps": 24,
                    "graph_epochs": 240,
                    "graph_hidden_dim": 128,
                    "forecaster_hidden_dim": 160,
                    "forecaster_layers": 3,
                    "forecaster_batch_size": 256,
                },
            ]

    leaderboard = []
    best_artifacts = None
    best_score = float("-inf")

    for config_idx, config in enumerate(search_plan):
        artifacts = run_agent_training_loops(
            device=device,
            loops=config["loops"],
            seed=seed + config_idx * 11,
            bootstrap_episodes=config["bootstrap_episodes"],
            bootstrap_steps=config["bootstrap_steps"],
            forecaster_epochs=config["forecaster_epochs"],
            rl_episodes=config["rl_episodes"],
            rl_steps=config["rl_steps"],
            graph_epochs=config["graph_epochs"],
            graph_hidden_dim=config["graph_hidden_dim"],
            forecaster_hidden_dim=config["forecaster_hidden_dim"],
            forecaster_layers=config["forecaster_layers"],
            forecaster_batch_size=config["forecaster_batch_size"],
        )
        aggregate_metrics = evaluate_simulation(artifacts["signals_df"])
        objective = defense_objective(aggregate_metrics)
        leaderboard.append(
            {
                "config_id": config_idx,
                **config,
                **aggregate_metrics,
                "defense_objective": objective,
            }
        )
        if objective > best_score:
            best_score = objective
            best_artifacts = artifacts
            best_artifacts["best_config"] = dict(config)
            best_artifacts["best_defense_objective"] = objective

    leaderboard_df = pd.DataFrame(leaderboard).sort_values("defense_objective", ascending=False).reset_index(drop=True)
    best_artifacts["leaderboard_df"] = leaderboard_df
    return best_artifacts


def _local_refinement_plan(base_config: dict[str, int], device: torch.device) -> list[dict[str, int]]:
    hidden_candidates = sorted(set([max(32, base_config["graph_hidden_dim"] - 32), base_config["graph_hidden_dim"], base_config["graph_hidden_dim"] + 32]))
    forecaster_candidates = sorted(set([max(48, base_config["forecaster_hidden_dim"] - 32), base_config["forecaster_hidden_dim"], base_config["forecaster_hidden_dim"] + 32]))
    epoch_candidates = sorted(set([max(12, base_config["forecaster_epochs"] - 8), base_config["forecaster_epochs"], base_config["forecaster_epochs"] + 10]))
    rl_episode_candidates = sorted(set([max(40, base_config["rl_episodes"] - 20), base_config["rl_episodes"], base_config["rl_episodes"] + 20]))
    loop_candidates = sorted(set([max(2, base_config["loops"] - 1), base_config["loops"], base_config["loops"] + 1]))
    batch_step = 128 if device.type == "cuda" else 64
    batch_candidates = sorted(set([max(32, base_config["forecaster_batch_size"] - batch_step), base_config["forecaster_batch_size"], base_config["forecaster_batch_size"] + batch_step]))

    variants = []
    for loops in loop_candidates:
        for graph_hidden_dim in hidden_candidates:
            for forecaster_hidden_dim in forecaster_candidates:
                variants.append(
                    {
                        "loops": loops,
                        "bootstrap_episodes": base_config["bootstrap_episodes"],
                        "bootstrap_steps": base_config["bootstrap_steps"],
                        "forecaster_epochs": random.choice(epoch_candidates),
                        "rl_episodes": random.choice(rl_episode_candidates),
                        "rl_steps": base_config["rl_steps"],
                        "graph_epochs": base_config["graph_epochs"] + (20 if graph_hidden_dim > base_config["graph_hidden_dim"] else 0),
                        "graph_hidden_dim": graph_hidden_dim,
                        "forecaster_hidden_dim": forecaster_hidden_dim,
                        "forecaster_layers": base_config["forecaster_layers"],
                        "forecaster_batch_size": random.choice(batch_candidates),
                    }
                )
    unique = []
    seen = set()
    for variant in variants:
        key = tuple(sorted(variant.items()))
        if key not in seen:
            seen.add(key)
            unique.append(variant)
    return unique[:6]


def optimize_agent_training_adaptive(
    device: torch.device,
    broad_search_plan: list[dict[str, int]] | None = None,
    search_plan: list[dict[str, int]] | None = None,
    seed: int = 42,
) -> dict[str, object]:
    if broad_search_plan is None and search_plan is not None:
        broad_search_plan = search_plan
    broad_results = optimize_agent_training(device=device, search_plan=broad_search_plan, seed=seed)
    best_config = dict(broad_results["best_config"])
    refinement_plan = _local_refinement_plan(best_config, device)
    refined_results = optimize_agent_training(device=device, search_plan=refinement_plan, seed=seed + 101)

    broad_board = broad_results["leaderboard_df"].copy()
    broad_board["phase"] = "broad"
    refined_board = refined_results["leaderboard_df"].copy()
    refined_board["phase"] = "refine"
    combined_board = pd.concat([broad_board, refined_board], ignore_index=True).sort_values("defense_objective", ascending=False).reset_index(drop=True)

    if refined_results["best_defense_objective"] >= broad_results["best_defense_objective"]:
        winner = refined_results
    else:
        winner = broad_results

    winner["leaderboard_df"] = combined_board
    winner["broad_leaderboard_df"] = broad_board
    winner["refined_leaderboard_df"] = refined_board
    winner["broad_best_config"] = broad_results["best_config"]
    winner["refined_best_config"] = refined_results["best_config"]
    winner["search_mode"] = "adaptive"
    return winner


def plot_training(episode_df: pd.DataFrame, events_df: pd.DataFrame) -> None:
    sns.set_theme(style="darkgrid")
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    sns.lineplot(data=episode_df, x="episode", y="red_reward", ax=axes[0, 0], label="Red Team")
    sns.lineplot(data=episode_df, x="episode", y="blue_reward", ax=axes[0, 0], label="Cortex")
    axes[0, 0].set_title("Dual RL rewards")
    sns.lineplot(data=episode_df, x="episode", y="early_detections", ax=axes[0, 1], color="#2ca02c")
    axes[0, 1].set_title("Early detections per episode")
    sns.histplot(events_df["fused_signal"], ax=axes[1, 0], bins=20, color="#d62728")
    axes[1, 0].set_title("Fused Cortex signals")
    action_counts = events_df["attacker_action"].value_counts().reset_index()
    action_counts.columns = ["action", "count"]
    sns.barplot(data=action_counts, x="action", y="count", ax=axes[1, 1], color="#1f77b4")
    axes[1, 1].tick_params(axis="x", rotation=30)
    axes[1, 1].set_title("Attacker action mix")
    plt.tight_layout()


def plot_predictions(events_df: pd.DataFrame) -> None:
    pivot = (
        events_df.groupby(["scenario", "predicted_next_action"])
        .size()
        .reset_index(name="count")
        .pivot(index="scenario", columns="predicted_next_action", values="count")
        .fillna(0)
    )
    plt.figure(figsize=(12, 5))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="mako")
    plt.title("Predicted next attacker actions by scenario")
    plt.tight_layout()


def plot_privilege_token_dynamics(signals_df: pd.DataFrame) -> None:
    sns.set_theme(style="darkgrid")
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    privilege_loop = (
        signals_df.groupby("training_loop")[["privilege_level", "detected_early", "blocked", "exfiltration_success"]]
        .mean()
        .reset_index()
    )
    sns.lineplot(data=privilege_loop, x="training_loop", y="privilege_level", marker="o", ax=axes[0], label="mean privilege")
    sns.lineplot(data=privilege_loop, x="training_loop", y="detected_early", marker="o", ax=axes[0], label="early detect")
    axes[0].set_title("Privilege escalation vs early detection")
    axes[0].set_xlabel("training loop")

    token_scenario = (
        signals_df.groupby("scenario")[["token_age_minutes", "token_remaining_ratio", "token_expired"]]
        .mean()
        .reset_index()
        .sort_values("token_age_minutes", ascending=False)
    )
    token_long = token_scenario.melt(id_vars="scenario", var_name="metric", value_name="value")
    sns.barplot(data=token_long, x="scenario", y="value", hue="metric", ax=axes[1])
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].set_title("Token time pressure by scenario")

    privilege_labels = ["session_user", "delegated_access", "privileged_operator", "admin"]
    privilege_counts = (
        signals_df["privilege_label"]
        .value_counts()
        .reindex(privilege_labels, fill_value=0)
        .reset_index()
    )
    privilege_counts.columns = ["privilege_label", "count"]
    sns.barplot(data=privilege_counts, x="privilege_label", y="count", ax=axes[2], color="#ff7f0e")
    axes[2].tick_params(axis="x", rotation=25)
    axes[2].set_title("Privilege label distribution")
    plt.tight_layout()


def plot_agent_loop_scores(signals_df: pd.DataFrame) -> None:
    score_cols = [
        "sentinel_score",
        "trust_engine_score",
        "threat_hunter_score",
        "graph_analyst_score",
        "anomaly_detector_score",
    ]
    score_df = (
        signals_df.groupby("training_loop")[score_cols]
        .mean()
        .reset_index()
        .melt(id_vars="training_loop", var_name="agent", value_name="mean_score")
    )
    plt.figure(figsize=(12, 5))
    sns.lineplot(data=score_df, x="training_loop", y="mean_score", hue="agent", marker="o")
    plt.title("Average Cortex agent scores by training loop")
    plt.xlabel("training loop")
    plt.ylabel("mean score")
    plt.tight_layout()


def export_artifacts(export_dir: str | Path, graph_model: GraphRiskGCN, forecaster: AttackForecaster, attacker: QLearningAgent, defender: QLearningAgent, events_df: pd.DataFrame, episode_df: pd.DataFrame, metrics: dict[str, object]) -> dict[str, str]:
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)
    graph_model_path = export_path / "graph_risk_gcn.pt"
    forecaster_path = export_path / "attack_forecaster.pt"
    attacker_path = export_path / "red_team_q_table.json"
    defender_path = export_path / "sentinel_q_table.json"
    events_path = export_path / "simulation_events.csv"
    episode_path = export_path / "episode_metrics.csv"
    metrics_path = export_path / "evaluation_metrics.json"

    torch.save(graph_model.state_dict(), graph_model_path)
    torch.save(forecaster.state_dict(), forecaster_path)
    attacker_path.write_text(json.dumps({str(key): value.tolist() for key, value in attacker.q.items()}, indent=2), encoding="utf-8")
    defender_path.write_text(json.dumps({str(key): value.tolist() for key, value in defender.q.items()}, indent=2), encoding="utf-8")
    events_df.to_csv(events_path, index=False)
    episode_df.to_csv(episode_path, index=False)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return {
        "graph_model": str(graph_model_path),
        "attack_forecaster": str(forecaster_path),
        "red_team_q_table": str(attacker_path),
        "sentinel_q_table": str(defender_path),
        "simulation_events": str(events_path),
        "episode_metrics": str(episode_path),
        "evaluation_metrics": str(metrics_path),
    }
