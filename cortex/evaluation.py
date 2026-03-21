from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def compute_metrics(runtime_df: pd.DataFrame, reward_curve: list[float]) -> dict[str, float]:
    tp = int(((runtime_df["label_attack"] == 1) & (runtime_df["pred_attack"] == 1)).sum())
    fp = int(((runtime_df["label_attack"] == 0) & (runtime_df["pred_attack"] == 1)).sum())
    fn = int(((runtime_df["label_attack"] == 1) & (runtime_df["pred_attack"] == 0)).sum())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {
        "precision": precision,
        "recall": recall,
        "average_reward": float(sum(reward_curve) / max(1, len(reward_curve))),
        "final_reward": float(reward_curve[-1] if reward_curve else 0.0),
        "improvement": float((reward_curve[-1] - reward_curve[0]) if len(reward_curve) >= 2 else 0.0),
        "convergence_gap": float(abs(reward_curve[-1] - reward_curve[-5]) if len(reward_curve) >= 5 else 0.0),
    }


def plot_training(runtime_df: pd.DataFrame, reward_curve: list[float], export_dir: str | Path | None = None) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    pd.Series(reward_curve).plot(ax=axes[0], title="RL Reward Curve")
    runtime_df["action"].value_counts().plot(kind="bar", ax=axes[1], title="Sentinel Actions")
    runtime_df["episode_error_corrected"].cumsum().plot(ax=axes[2], title="Corrected Errors")
    plt.tight_layout()
    if export_dir:
        target = Path(export_dir)
        target.mkdir(parents=True, exist_ok=True)
        fig.savefig(target / "training_visualization.png", dpi=160)
    plt.close(fig)

