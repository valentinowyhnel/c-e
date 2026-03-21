from __future__ import annotations

import numpy as np
import pandas as pd

STATE_COLUMNS = [
    "anomaly_score",
    "novelty_score",
    "trust_score",
    "temporal_score",
    "graph_score",
    "campaign_score",
]


def extract_features(event: dict[str, object] | pd.Series) -> dict[str, float]:
    row = event if isinstance(event, dict) else event.to_dict()
    return {
        "anomaly_score": float(row["anomaly_score"]),
        "novelty_score": float(row["novelty_score"]),
        "trust_score": float(row["trust_score"]),
        "trust_risk": 1.0 - float(row["trust_score"]),
        "temporal_score": float(row["temporal_score"]),
        "graph_score": float(row["graph_score"]),
        "campaign_score": float(row["campaign_score"]),
    }


def build_state(scores: dict[str, float]) -> np.ndarray:
    return np.array(
        [
            scores["anomaly_score"],
            scores["novelty_score"],
            scores["trust_score"],
            scores["temporal_score"],
            scores["graph_score"],
            scores["campaign_score"],
        ],
        dtype=np.float32,
    )


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame["risk_blend"] = (
        frame["anomaly_score"] * 0.25
        + frame["novelty_score"] * 0.20
        + (1.0 - frame["trust_score"]) * 0.20
        + frame["temporal_score"] * 0.15
        + frame["graph_score"] * 0.10
        + frame["campaign_score"] * 0.10
    )
    return frame
