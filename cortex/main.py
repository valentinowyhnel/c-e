from __future__ import annotations

import json

from .evaluation import compute_metrics, plot_training
from .training_pipeline import run_training


def main() -> int:
    results = run_training()
    metrics = compute_metrics(results["runtime_df"], results["reward_curve"])
    plot_training(results["runtime_df"], results["reward_curve"], results["export_dir"])
    print(json.dumps(metrics, indent=2))
    print(results["export_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
