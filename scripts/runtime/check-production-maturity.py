from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared" / "cortex-core"))

from cortex_core.maturity import production_maturity_blockers  # noqa: E402


def main() -> int:
    blockers = production_maturity_blockers()
    if blockers:
        print("production_maturity=blocked")
        for blocker in blockers:
            print(f"blocker:{blocker}")
        return 1

    print("production_maturity=ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
