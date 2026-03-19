from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_core.state_machine import IsolationState, transition_isolation_state


def test_invalid_transition_rejected() -> None:
    result = transition_isolation_state(
        IsolationState.FREE,
        IsolationState.ISOLATED,
        "unsafe_direct_jump",
    )
    assert result.allowed is False
    assert result.from_state is IsolationState.FREE
    assert result.to_state is IsolationState.FREE
    assert "invalid_transition" in result.reason


def test_valid_transition_allowed() -> None:
    result = transition_isolation_state(
        IsolationState.OBSERVATION,
        IsolationState.RESTRICTED,
        "policy_escalation",
    )
    assert result.allowed is True
    assert result.from_state is IsolationState.OBSERVATION
    assert result.to_state is IsolationState.RESTRICTED
