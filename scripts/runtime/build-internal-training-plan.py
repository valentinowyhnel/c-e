from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "services" / "python" / "cortex-sentinel-machine"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.training import AttackKnowledgeCurator  # noqa: E402
from app.training.internal_sources import load_internal_corpus  # noqa: E402
from app.training.knowledge_curator import load_known_records  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a defensive Cortex training plan from internal audited intelligence sources."
    )
    parser.add_argument("--audit", help="JSON array exported from cortex-audit /v1/events", default=None)
    parser.add_argument("--drifts", help="JSON array of AD drift events", default=None)
    parser.add_argument("--attack-paths", help="JSON array of BloodHound path summaries", default=None)
    parser.add_argument("--soc-reports", help="JSON array of normalized SOC reports", default=None)
    parser.add_argument("--known", help="Optional JSON array of already-ingested attack fingerprints", default=None)
    parser.add_argument("--output", help="Optional output path. Defaults to stdout.", default=None)
    args = parser.parse_args()

    samples, stats = load_internal_corpus(
        audit_path=args.audit,
        drift_path=args.drifts,
        bloodhound_path=args.attack_paths,
        soc_reports_path=args.soc_reports,
    )
    plan = AttackKnowledgeCurator(load_known_records(args.known)).build_plan(samples).as_dict()
    plan["sources"] = stats.as_dict()
    rendered = json.dumps(plan, indent=2)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
