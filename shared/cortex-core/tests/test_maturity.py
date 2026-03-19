from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_core.maturity import production_maturity_blockers


def test_production_maturity_blockers_report_non_prod_capabilities():
    blockers = production_maturity_blockers()

    assert blockers
    assert "ad_destructive_writes=stubbed" in blockers
    assert "irreversible_containment=experimental" in blockers
