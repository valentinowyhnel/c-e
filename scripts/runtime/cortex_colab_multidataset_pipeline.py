from __future__ import annotations

import json
import math
import random
import urllib.error
import urllib.request
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

try:
    from torch_geometric.data import Data as PyGData
    from torch_geometric.nn import GCNConv
except Exception:  # pragma: no cover
    PyGData = None
    GCNConv = None


DATASET_NAMES = ["CIC-IDS2017", "UNSW-NB15", "CERT-Inside", "LANL-Subset", "TON_IoT"]
AGENT_NAMES = ["Sentinel", "Threat Hunter", "Trust Engine", "Graph Analyst", "Anomaly Detector"]
NUMERIC_FEATURES = [
    "duration",
    "bytes_out",
    "bytes_in",
    "auth_failures",
    "process_depth",
    "failed_ratio",
    "temporal_drift",
    "graph_expansion",
    "novelty",
    "baseline_deviation",
    "insider_score",
    "admin_anomaly",
    "edge_suspicion",
    "data_trust_score",
]


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def detect_device() -> dict[str, object]:
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        return {
            "device": "cuda",
            "gpu_name": torch.cuda.get_device_name(0),
            "vram_gb": round(props.total_memory / (1024 ** 3), 2),
        }
    return {"device": "cpu", "gpu_name": "CPU fallback", "vram_gb": 0.0}


def _random_ip(rng: random.Random, edge_bias: bool = False) -> str:
    prefix = 10 if edge_bias else rng.choice([10, 172, 192])
    return f"{prefix}.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"


def generate_synthetic_dataset(name: str, rows: int = 2500, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    users = [f"user-{idx}" for idx in range(32)]
    devices = [f"device-{idx}" for idx in range(40)]
    services = [f"service-{idx}" for idx in range(12)]
    resources = [f"resource-{idx}" for idx in range(18)]
    records = []
    base_time = pd.Timestamp("2025-01-01")

    for idx in range(rows):
        scenario = rng.choices(
            ["benign", "zero_day", "low_slow", "multi_step", "insider"],
            weights=[0.72, 0.06, 0.08, 0.09, 0.05],
        )[0]
        user = rng.choice(users)
        device = rng.choice(devices)
        service = rng.choice(services)
        resource = rng.choice(resources)
        is_admin = int(user.endswith(("0", "1", "2")))
        attack = int(scenario != "benign")
        zero_day = int(scenario == "zero_day")
        insider = int(scenario == "insider")
        low_slow = int(scenario == "low_slow")
        multi_step = int(scenario == "multi_step")
        event_type = rng.choice(["auth", "api", "file", "process", "dns", "network_scan", "db_query"])
        duration = rng.uniform(0.1, 5.0) if not attack else rng.uniform(1.0, 25.0)
        bytes_out = rng.uniform(200, 4000) if not attack else rng.uniform(1200, 25000)
        bytes_in = rng.uniform(200, 6000) if not attack else rng.uniform(800, 30000)
        auth_failures = rng.randint(0, 1) if not attack else rng.randint(0, 6)
        process_depth = rng.randint(1, 4) if not attack else rng.randint(2, 9)
        edge_flag = int(device.endswith(("8", "9")))
        timestamp = base_time + pd.Timedelta(minutes=idx * rng.randint(1, 3) + rng.randint(0, 5))
        if low_slow:
            timestamp = base_time + pd.Timedelta(minutes=idx * 8 + rng.randint(0, 2))
        records.append(
            {
                "dataset": name,
                "event_id": f"{name.lower().replace(' ', '-')}-{idx}",
                "timestamp": timestamp,
                "user": user,
                "device": device,
                "service": service,
                "resource": resource,
                "src_ip": _random_ip(rng, edge_bias=bool(edge_flag)),
                "dst_ip": _random_ip(rng, edge_bias=attack == 1),
                "protocol": rng.choice(["tcp", "udp", "http", "https", "dns"]),
                "event_type": event_type,
                "duration": duration,
                "bytes_out": bytes_out,
                "bytes_in": bytes_in,
                "auth_failures": auth_failures,
                "process_depth": process_depth,
                "is_admin": is_admin,
                "edge_flag": edge_flag,
                "label_attack": attack,
                "label_zero_day": zero_day,
                "label_insider": insider,
                "label_low_slow": low_slow,
                "label_multi_step": multi_step,
            }
        )
    return pd.DataFrame(records)


def download_or_generate_datasets(data_dir: str | Path, dataset_urls: dict[str, str] | None = None, rows_per_dataset: int = 2500) -> dict[str, pd.DataFrame]:
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    dataset_urls = dataset_urls or {}
    loaded: dict[str, pd.DataFrame] = {}
    for offset, name in enumerate(DATASET_NAMES):
        csv_path = data_path / f"{name.lower().replace('-', '_').replace(' ', '_')}.csv"
        if csv_path.exists():
            loaded[name] = pd.read_csv(csv_path, parse_dates=["timestamp"])
            continue
        url = dataset_urls.get(name)
        if url:
            try:
                urllib.request.urlretrieve(url, csv_path)
                loaded[name] = pd.read_csv(csv_path, parse_dates=["timestamp"])
                continue
            except (urllib.error.URLError, ValueError, OSError):
                pass
        loaded[name] = generate_synthetic_dataset(name, rows=rows_per_dataset, seed=42 + offset)
        loaded[name].to_csv(csv_path, index=False)
    return loaded


def merge_datasets(dataset_map: dict[str, pd.DataFrame]) -> pd.DataFrame:
    df = pd.concat(dataset_map.values(), ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def score_data_trust(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    duplicate_mask = work.duplicated(subset=["user", "device", "service", "resource", "timestamp", "event_type"])
    missing_ratio = work.isna().mean(axis=1)
    coherence = (
        work["duration"].ge(0).astype(float)
        * work["bytes_out"].ge(0).astype(float)
        * work["bytes_in"].ge(0).astype(float)
        * work["protocol"].isin(["tcp", "udp", "http", "https", "dns"]).astype(float)
    )
    extreme = (
        (work["bytes_out"] > work["bytes_out"].quantile(0.995))
        | (work["bytes_in"] > work["bytes_in"].quantile(0.995))
        | (work["process_depth"] > work["process_depth"].quantile(0.995))
    )
    temporal_violation = work["timestamp"].isna().astype(float)
    trust = (
        0.40 * coherence
        + 0.25 * (1.0 - duplicate_mask.astype(float))
        + 0.20 * (1.0 - missing_ratio.clip(0, 1))
        + 0.15 * (1.0 - temporal_violation)
        - 0.15 * extreme.astype(float)
    ).clip(0.0, 1.0)
    work["data_trust_score"] = trust
    work["data_trust_bucket"] = np.select(
        [trust >= 0.72, trust >= 0.45],
        ["accepted", "quarantined"],
        default="rejected",
    )
    work["duplicate_flag"] = duplicate_mask.astype(int)
    work["extreme_flag"] = extreme.astype(int)
    return work


def filter_and_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    accepted = df.loc[df["data_trust_bucket"] == "accepted"].copy()
    quarantine = df.loc[df["data_trust_bucket"] != "accepted"].copy()
    accepted["timestamp"] = pd.to_datetime(accepted["timestamp"], errors="coerce")
    accepted = accepted.dropna(subset=["timestamp"]).reset_index(drop=True)
    accepted["failed_ratio"] = accepted["auth_failures"] / (accepted["process_depth"] + 1.0)
    return accepted, quarantine


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy().sort_values("timestamp").reset_index(drop=True)
    user_avg_bytes = work.groupby("user")["bytes_out"].transform("mean")
    device_avg_duration = work.groupby("device")["duration"].transform("mean")
    service_popularity = work.groupby("service")["event_id"].transform("count") / max(1, len(work))
    event_counts = Counter(work["event_type"])
    work["temporal_drift"] = (
        work.groupby("user")["timestamp"].diff().dt.total_seconds().fillna(0).clip(0, 86400) / 86400.0
    )
    work["graph_expansion"] = (
        work.groupby("user")[["device", "service", "resource"]]
        .transform(lambda col: col.factorize()[0])
        .sum(axis=1)
        / 30.0
    ).clip(0, 1)
    work["novelty"] = work["event_type"].map(lambda item: 1.0 / (1.0 + event_counts[item]))
    work["baseline_deviation"] = (((work["bytes_out"] - user_avg_bytes).abs() / user_avg_bytes.replace(0, 1.0))).clip(0, 5) / 5.0
    work["insider_score"] = (0.6 * work["label_insider"] + 0.2 * work["is_admin"] + 0.2 * work["baseline_deviation"]).clip(0, 1)
    work["admin_anomaly"] = (work["is_admin"] * (0.4 * work["failed_ratio"] + 0.6 * work["baseline_deviation"])).clip(0, 1)
    work["edge_suspicion"] = (0.5 * work["edge_flag"] + 0.2 * work["label_zero_day"] + 0.3 * work["graph_expansion"]).clip(0, 1)
    work["behavior_drift"] = (((work["duration"] - device_avg_duration).abs() / device_avg_duration.replace(0, 1.0))).clip(0, 5) / 5.0
    work["service_rarity"] = (1.0 - service_popularity).clip(0, 1)
    work["zero_day_proxy"] = (0.50 * work["novelty"] + 0.20 * work["edge_suspicion"] + 0.30 * work["label_zero_day"]).clip(0, 1)
    return work


def select_data_by_agent(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "Sentinel": df.loc[(df["label_multi_step"] == 1) | (df["temporal_drift"] > 0.25) | (df["graph_expansion"] > 0.30)].copy(),
        "Threat Hunter": df.loc[(df["zero_day_proxy"] > 0.40) | (df["novelty"] > 0.04)].copy(),
        "Trust Engine": df.loc[(df["is_admin"] == 1) | (df["insider_score"] > 0.30) | (df["admin_anomaly"] > 0.25)].copy(),
        "Graph Analyst": df.loc[(df["graph_expansion"] > 0.18) | (df["service_rarity"] > 0.85)].copy(),
        "Anomaly Detector": df.loc[(df["baseline_deviation"] > 0.12) | (df["failed_ratio"] > 0.10) | (df["edge_suspicion"] > 0.30)].copy(),
    }


@dataclass
class GraphBundle:
    graph: nx.Graph
    node_frame: pd.DataFrame
    edge_frame: pd.DataFrame
    data: object | None
    node_index: dict[str, int]


def build_cortex_graph(df: pd.DataFrame) -> GraphBundle:
    graph = nx.Graph()
    node_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"events": 0.0, "risk": 0.0, "attack": 0.0})
    edges = []
    for row in df.itertuples(index=False):
        nodes = {
            row.user: "user",
            row.device: "device",
            row.service: "service",
            row.resource: "resource",
        }
        for node, role in nodes.items():
            graph.add_node(node, role=role)
            node_stats[node]["events"] += 1.0
            node_stats[node]["risk"] += float(row.baseline_deviation + row.edge_suspicion + row.zero_day_proxy)
            node_stats[node]["attack"] += float(row.label_attack)
        tuples = [
            (row.user, row.device, "access"),
            (row.device, row.service, "communication"),
            (row.service, row.resource, "process"),
        ]
        for left, right, relation in tuples:
            graph.add_edge(left, right, relation=relation)
            edges.append({"src": left, "dst": right, "relation": relation, "event_id": row.event_id})

    pagerank = nx.pagerank(graph)
    betweenness = nx.betweenness_centrality(graph)
    node_rows = []
    node_index = {node: idx for idx, node in enumerate(graph.nodes())}
    for node, data in graph.nodes(data=True):
        role = data["role"]
        stats = node_stats[node]
        role_vector = [float(role == value) for value in ["user", "device", "service", "resource"]]
        node_rows.append(
            {
                "node": node,
                "role": role,
                "events": stats["events"],
                "avg_risk": stats["risk"] / max(1.0, stats["events"]),
                "pagerank": pagerank[node],
                "betweenness": betweenness[node],
                "label_attack": int(stats["attack"] > 0),
                "f_user": role_vector[0],
                "f_device": role_vector[1],
                "f_service": role_vector[2],
                "f_resource": role_vector[3],
            }
        )
    node_frame = pd.DataFrame(node_rows)
    edge_frame = pd.DataFrame(edges)

    pyg_data = None
    if PyGData is not None and GCNConv is not None:
        edge_index = []
        for left, right in graph.edges():
            edge_index.append([node_index[left], node_index[right]])
            edge_index.append([node_index[right], node_index[left]])
        x = torch.tensor(
            node_frame[["events", "avg_risk", "pagerank", "betweenness", "f_user", "f_device", "f_service", "f_resource"]].to_numpy(dtype=np.float32),
            dtype=torch.float32,
        )
        y = torch.tensor(node_frame["label_attack"].to_numpy(dtype=np.float32), dtype=torch.float32)
        pyg_data = PyGData(x=x, edge_index=torch.tensor(edge_index, dtype=torch.long).t().contiguous(), y=y)
    return GraphBundle(graph=graph, node_frame=node_frame, edge_frame=edge_frame, data=pyg_data, node_index=node_index)


class Autoencoder(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, 64), nn.ReLU(), nn.Linear(64, 16))
        self.decoder = nn.Sequential(nn.Linear(16, 64), nn.ReLU(), nn.Linear(64, input_dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


class TemporalLSTM(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 48):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.head = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (hidden, _) = self.lstm(x)
        return self.head(hidden[-1]).squeeze(-1)


class GraphDetector(nn.Module):
    def __init__(self, in_dim: int):
        super().__init__()
        if GCNConv is None:
            self.gcn1 = nn.Linear(in_dim, 32)
            self.gcn2 = nn.Linear(32, 16)
            self.out = nn.Linear(16, 1)
            self.pyg = False
        else:
            self.gcn1 = GCNConv(in_dim, 32)
            self.gcn2 = GCNConv(32, 16)
            self.out = nn.Linear(16, 1)
            self.pyg = True

    def forward(self, data: object) -> tuple[torch.Tensor, torch.Tensor]:
        if self.pyg:
            x, edge_index = data.x, data.edge_index
            x = F.relu(self.gcn1(x, edge_index))
            embedding = F.relu(self.gcn2(x, edge_index))
        else:
            x = F.relu(self.gcn1(data))
            embedding = F.relu(self.gcn2(x))
        logits = self.out(embedding).squeeze(-1)
        return logits, embedding


def _train_loop(model: nn.Module, loader: DataLoader, optimizer: torch.optim.Optimizer, device: torch.device, loss_fn, epochs: int = 12, early_stop: int = 3) -> list[float]:
    best = float("inf")
    stale = 0
    history = []
    for _ in range(epochs):
        model.train()
        running = 0.0
        total = 0
        for batch in loader:
            batch = [item.to(device) for item in batch]
            optimizer.zero_grad()
            loss = loss_fn(*batch)
            loss.backward()
            optimizer.step()
            running += float(loss.item()) * len(batch[0])
            total += len(batch[0])
        epoch_loss = running / max(1, total)
        history.append(epoch_loss)
        if epoch_loss + 1e-5 < best:
            best = epoch_loss
            stale = 0
        else:
            stale += 1
            if stale >= early_stop:
                break
    return history


def train_autoencoder(df: pd.DataFrame, device: torch.device) -> tuple[Autoencoder, StandardScaler, list[float]]:
    scaler = StandardScaler()
    x = scaler.fit_transform(df[NUMERIC_FEATURES].to_numpy(dtype=np.float32))
    tensor = torch.tensor(x, dtype=torch.float32)
    loader = DataLoader(TensorDataset(tensor, tensor), batch_size=256, shuffle=True, pin_memory=device.type == "cuda")
    model = Autoencoder(input_dim=tensor.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    history = _train_loop(
        model,
        loader,
        optimizer,
        device,
        lambda batch_x, batch_y: F.mse_loss(model(batch_x), batch_y),
        epochs=16,
        early_stop=4,
    )
    return model, scaler, history


def train_isolation_forest(df: pd.DataFrame) -> IsolationForest:
    model = IsolationForest(n_estimators=220, contamination=0.12, random_state=42)
    model.fit(df[NUMERIC_FEATURES])
    return model


def build_temporal_sequences(df: pd.DataFrame, sequence_len: int = 6) -> tuple[torch.Tensor, torch.Tensor]:
    sequences = []
    labels = []
    for _, user_df in df.sort_values("timestamp").groupby("user"):
        values = user_df[NUMERIC_FEATURES].to_numpy(dtype=np.float32)
        targets = user_df["label_attack"].to_numpy(dtype=np.float32)
        if len(values) <= sequence_len:
            continue
        for idx in range(len(values) - sequence_len):
            sequences.append(values[idx : idx + sequence_len])
            labels.append(targets[idx + sequence_len])
    return torch.tensor(np.array(sequences), dtype=torch.float32), torch.tensor(np.array(labels), dtype=torch.float32)


def train_temporal_model(df: pd.DataFrame, device: torch.device) -> tuple[TemporalLSTM, StandardScaler, list[float]]:
    scaler = StandardScaler()
    scaled = df.copy()
    scaled[NUMERIC_FEATURES] = scaler.fit_transform(df[NUMERIC_FEATURES].to_numpy(dtype=np.float32))
    sequences, labels = build_temporal_sequences(scaled)
    loader = DataLoader(TensorDataset(sequences, labels), batch_size=128, shuffle=True, pin_memory=device.type == "cuda")
    model = TemporalLSTM(input_dim=len(NUMERIC_FEATURES)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    history = _train_loop(
        model,
        loader,
        optimizer,
        device,
        lambda batch_x, batch_y: F.binary_cross_entropy_with_logits(model(batch_x), batch_y),
        epochs=14,
        early_stop=4,
    )
    return model, scaler, history


def train_graph_model(bundle: GraphBundle, device: torch.device) -> tuple[GraphDetector, np.ndarray, list[float]]:
    model = GraphDetector(in_dim=8).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    history = []
    if bundle.data is not None:
        data = bundle.data
        data.x = data.x.to(device)
        data.edge_index = data.edge_index.to(device)
        labels = data.y.to(device)
        for _ in range(120):
            logits, _ = model(data)
            loss = loss_fn(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            history.append(float(loss.item()))
        with torch.no_grad():
            logits, _ = model(data)
    else:
        x = torch.tensor(
            bundle.node_frame[["events", "avg_risk", "pagerank", "betweenness", "f_user", "f_device", "f_service", "f_resource"]].to_numpy(dtype=np.float32),
            dtype=torch.float32,
            device=device,
        )
        labels = torch.tensor(bundle.node_frame["label_attack"].to_numpy(dtype=np.float32), dtype=torch.float32, device=device)
        for _ in range(120):
            logits, _ = model(x)
            loss = loss_fn(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            history.append(float(loss.item()))
        with torch.no_grad():
            logits, _ = model(x)
    return model, torch.sigmoid(logits).detach().cpu().numpy(), history


def train_all_models(df: pd.DataFrame, bundle: GraphBundle, device: torch.device) -> dict[str, object]:
    autoencoder, ae_scaler, ae_history = train_autoencoder(df, device)
    isolation = train_isolation_forest(df)
    temporal, temporal_scaler, temporal_history = train_temporal_model(df, device)
    graph_model, graph_scores, graph_history = train_graph_model(bundle, device)
    return {
        "autoencoder": autoencoder,
        "ae_scaler": ae_scaler,
        "ae_history": ae_history,
        "isolation_forest": isolation,
        "temporal_model": temporal,
        "temporal_scaler": temporal_scaler,
        "temporal_history": temporal_history,
        "graph_model": graph_model,
        "graph_scores": graph_scores,
        "graph_history": graph_history,
    }


def score_events(df: pd.DataFrame, bundle: GraphBundle, models: dict[str, object], device: torch.device) -> pd.DataFrame:
    work = df.copy()
    ae_scaler: StandardScaler = models["ae_scaler"]
    temporal_scaler: StandardScaler = models["temporal_scaler"]
    scaled = ae_scaler.transform(work[NUMERIC_FEATURES].to_numpy(dtype=np.float32))
    autoencoder: Autoencoder = models["autoencoder"]
    autoencoder.eval()
    with torch.no_grad():
        reconstructed = autoencoder(torch.tensor(scaled, dtype=torch.float32, device=device)).cpu().numpy()
    mse = np.mean(np.square(scaled - reconstructed), axis=1)
    work["anomaly_score"] = (mse / (mse.max() + 1e-6)).clip(0, 1)

    forest: IsolationForest = models["isolation_forest"]
    if_scores = -forest.decision_function(work[NUMERIC_FEATURES])
    if_scores = 1.0 / (1.0 + np.exp(-4 * if_scores))
    work["novelty_score"] = np.clip(0.55 * work["novelty"] + 0.45 * if_scores, 0, 1)

    temporal = work.copy()
    temporal[NUMERIC_FEATURES] = temporal_scaler.transform(temporal[NUMERIC_FEATURES].to_numpy(dtype=np.float32))
    seq_x, _ = build_temporal_sequences(temporal)
    temporal_scores = np.zeros(len(work), dtype=np.float32)
    temporal_model: TemporalLSTM = models["temporal_model"]
    temporal_model.eval()
    if len(seq_x) > 0:
        with torch.no_grad():
            probs = torch.sigmoid(temporal_model(seq_x.to(device))).cpu().numpy()
        temporal_scores[-len(probs):] = probs
    work["temporal_score"] = temporal_scores

    node_scores = pd.Series(models["graph_scores"], index=bundle.node_frame["node"]).to_dict()
    work["graph_score"] = work.apply(
        lambda row: float(
            np.clip(
                0.4 * node_scores.get(row["user"], 0.2)
                + 0.2 * node_scores.get(row["device"], 0.2)
                + 0.2 * node_scores.get(row["service"], 0.2)
                + 0.2 * node_scores.get(row["resource"], 0.2),
                0,
                1,
            )
        ),
        axis=1,
    )
    work["trust_score"] = np.clip(
        1.0
        - (
            0.30 * work["insider_score"]
            + 0.25 * work["admin_anomaly"]
            + 0.20 * work["edge_suspicion"]
            + 0.15 * work["baseline_deviation"]
            + 0.10 * (1.0 - work["data_trust_score"])
        ),
        0,
        1,
    )
    work["reasoning_score"] = np.clip(
        0.24 * work["anomaly_score"]
        + 0.22 * work["novelty_score"]
        + 0.18 * work["temporal_score"]
        + 0.18 * work["graph_score"]
        + 0.18 * (1.0 - work["trust_score"]),
        0,
        1,
    )
    work["detection_score"] = np.clip(
        0.35 * work["reasoning_score"]
        + 0.20 * work["anomaly_score"]
        + 0.15 * work["temporal_score"]
        + 0.15 * work["graph_score"]
        + 0.15 * work["novelty_score"],
        0,
        1,
    )
    return work


def orchestrate_agents(scored_df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    work = scored_df.copy()
    messages: list[dict[str, object]] = []
    assignments = []
    for row in work.itertuples(index=False):
        agent_scores = {
            "Sentinel": 0.45 * row.temporal_score + 0.35 * row.graph_expansion + 0.20 * row.reasoning_score,
            "Threat Hunter": 0.50 * row.novelty_score + 0.30 * row.edge_suspicion + 0.20 * row.anomaly_score,
            "Trust Engine": 0.55 * (1.0 - row.trust_score) + 0.25 * row.insider_score + 0.20 * row.admin_anomaly,
            "Graph Analyst": 0.55 * row.graph_score + 0.25 * row.graph_expansion + 0.20 * row.zero_day_proxy,
            "Anomaly Detector": 0.60 * row.anomaly_score + 0.25 * row.novelty_score + 0.15 * row.baseline_deviation,
        }
        for agent, score in agent_scores.items():
            messages.append(
                {
                    "event_id": row.event_id,
                    "agent": agent,
                    "score": float(score),
                    "reasoning": f"{agent} analyzed event {row.event_id} and produced a risk signal.",
                    "priority": float(min(1.0, 0.60 * score + 0.40 * row.detection_score)),
                }
            )
        assignments.append(max(agent_scores, key=agent_scores.get))
    work["primary_agent"] = assignments
    work["risk_bucket"] = np.select(
        [work["detection_score"] >= 0.75, work["detection_score"] >= 0.55],
        ["critical", "high"],
        default="review",
    )
    return work, messages


def simulate_realtime(scored_df: pd.DataFrame, window: int = 120) -> pd.DataFrame:
    stream = scored_df.sort_values("timestamp").copy()
    stream["rolling_risk"] = stream["detection_score"].rolling(window=min(window, len(stream)), min_periods=1).mean()
    stream["rolling_attack_rate"] = stream["label_attack"].rolling(window=min(window, len(stream)), min_periods=1).mean()
    stream["simulated_action"] = np.where(stream["detection_score"] >= 0.75, "simulate_block", np.where(stream["detection_score"] >= 0.55, "simulate_challenge", "simulate_observe"))
    return stream


def continuous_training_update(scored_df: pd.DataFrame, replay_size: int = 512) -> pd.DataFrame:
    buffer = deque(maxlen=replay_size)
    adjusted = []
    running = 0.0
    for row in scored_df.itertuples(index=False):
        buffer.append(float(row.detection_score))
        running = 0.9 * running + 0.1 * float(row.detection_score)
        adjusted.append(float(min(1.0, 0.7 * row.detection_score + 0.3 * (sum(buffer) / len(buffer)))))
    updated = scored_df.copy()
    updated["continuous_detection_score"] = adjusted
    return updated


def validate_pipeline(df: pd.DataFrame) -> dict[str, float]:
    preds = (df["continuous_detection_score"] >= 0.58).astype(int)
    zero_preds = (df["novelty_score"] >= 0.55).astype(int)
    return {
        "precision": precision_score(df["label_attack"], preds, zero_division=0),
        "recall": recall_score(df["label_attack"], preds, zero_division=0),
        "f1": f1_score(df["label_attack"], preds, zero_division=0),
        "accuracy": accuracy_score(df["label_attack"], preds),
        "zero_day_recall": recall_score(df["label_zero_day"], zero_preds, zero_division=0),
        "false_positive_rate": float(df.loc[df["label_attack"] == 0, "continuous_detection_score"].ge(0.58).mean()),
    }


def plot_results(df: pd.DataFrame, bundle: GraphBundle) -> None:
    sns.set_theme(style="darkgrid")
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    sns.histplot(df["detection_score"], ax=axes[0, 0], bins=24, color="#d62728")
    axes[0, 0].set_title("Detection score distribution")
    sns.scatterplot(data=df.sample(min(3000, len(df))), x="anomaly_score", y="graph_score", hue="risk_bucket", ax=axes[0, 1], s=30)
    axes[0, 1].set_title("Anomaly vs graph score")
    top_attacks = df.groupby("dataset")["detection_score"].mean().sort_values(ascending=False).reset_index()
    sns.barplot(data=top_attacks, x="dataset", y="detection_score", ax=axes[1, 0], color="#1f77b4")
    axes[1, 0].tick_params(axis="x", rotation=25)
    axes[1, 0].set_title("Average detection score by dataset")
    sns.lineplot(data=df.sort_values("timestamp").tail(min(1200, len(df))), x="timestamp", y="continuous_detection_score", ax=axes[1, 1], color="#2ca02c")
    axes[1, 1].set_title("Realtime continuous score")
    plt.tight_layout()

    plt.figure(figsize=(12, 9))
    pos = nx.spring_layout(bundle.graph, seed=42)
    role_colors = {"user": "#1f77b4", "device": "#ff7f0e", "service": "#2ca02c", "resource": "#d62728"}
    colors = [role_colors[bundle.graph.nodes[node]["role"]] for node in bundle.graph.nodes()]
    nx.draw_networkx(bundle.graph, pos=pos, node_color=colors, node_size=320, font_size=7, edge_color="#bbbbbb")
    plt.title("Cortex entity graph")
    plt.axis("off")


def export_pipeline_artifacts(export_dir: str | Path, models: dict[str, object], accepted_df: pd.DataFrame, quarantine_df: pd.DataFrame, scored_df: pd.DataFrame, agent_messages: list[dict[str, object]], metrics: dict[str, float]) -> dict[str, str]:
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)
    accepted_path = export_path / "accepted_events.parquet"
    quarantine_path = export_path / "quarantined_events.parquet"
    scored_path = export_path / "scored_events.parquet"
    messages_path = export_path / "agent_messages.json"
    metrics_path = export_path / "validation_metrics.json"
    ae_path = export_path / "autoencoder.pt"
    temporal_path = export_path / "temporal_model.pt"
    graph_path = export_path / "graph_model.pt"

    accepted_df.to_parquet(accepted_path, index=False)
    quarantine_df.to_parquet(quarantine_path, index=False)
    scored_df.to_parquet(scored_path, index=False)
    messages_path.write_text(json.dumps(agent_messages[:5000], indent=2), encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    torch.save(models["autoencoder"].state_dict(), ae_path)
    torch.save(models["temporal_model"].state_dict(), temporal_path)
    torch.save(models["graph_model"].state_dict(), graph_path)
    return {
        "accepted_events": str(accepted_path),
        "quarantined_events": str(quarantine_path),
        "scored_events": str(scored_path),
        "agent_messages": str(messages_path),
        "metrics": str(metrics_path),
        "autoencoder": str(ae_path),
        "temporal_model": str(temporal_path),
        "graph_model": str(graph_path),
    }
