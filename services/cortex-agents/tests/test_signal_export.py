from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_agents.base import AgentResult
from cortex_agents.signal_export import build_agent_signal


def test_build_agent_signal_for_decision_agent() -> None:
    result = AgentResult(
        task_id="task-1",
        agent_id="decision",
        success=True,
        output={"decision": {"risk_level": 4, "advisory_only": True}},
        reasoning="Escalation requires human approval",
        actions_taken=[],
        requires_approval=True,
        approval_payload={"risk_level": 4},
        duration_ms=0,
        tokens_used=0,
    )
    signal = build_agent_signal({"type": "analyze_response_decision", "entity_id": "node-1", "entity_type": "machine"}, result)
    assert signal["entity_id"] == "node-1"
    assert signal["specialty"] == "response_decision"
    assert signal["risk_signal"] >= 0.7
    assert signal["requires_approval"] is True
