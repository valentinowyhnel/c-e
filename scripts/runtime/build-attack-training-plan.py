from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "services" / "python" / "cortex-sentinel-machine"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.training import AttackKnowledgeCurator  # noqa: E402
from app.training.knowledge_curator import load_known_records, load_samples  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a defensive Cortex training plan from real-world attack summaries."
    )
    parser.add_argument("samples", help="Path to a JSON array of attack knowledge samples.")
    parser.add_argument(
        "--known",
        help="Optional JSON array of already-ingested attack fingerprints to skip.",
        default=None,
    )
    parser.add_argument(
        "--output",
        help="Optional output path. Defaults to stdout.",
        default=None,
    )
    args = parser.parse_args()

    samples = load_samples(args.samples)
    known_records = load_known_records(args.known)
    plan = AttackKnowledgeCurator(known_records).build_plan(samples).as_dict()
    rendered = json.dumps(plan, indent=2)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
