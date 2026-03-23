from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
for root in (ROOT, CORE_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_agents.agents.decision import DecisionAgent


class FakeMCP:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def call_tool(self, tool_name: str, params: dict):
        if tool_name == "bh_get_attack_path":
            return {"result": {"has_path": True}}
        if tool_name == "bh_get_blast_radius":
            return {"result": {"score": 22}}
        if tool_name == "ad_validate_group_membership":
            return {"result": {"risk_level": 4}}
        return {"result": {}}

    async def complete(self, **kwargs):
        task = kwargs.get("task", "")
        return {"output": f"analysis:{task}", "model_used": kwargs.get("params", {}).get("force_model", "claude")}


def test_decision_agent_returns_standardized_deep_analysis() -> None:
    async def run() -> None:
        agent = DecisionAgent()
        agent.mcp = FakeMCP()
        result = await agent.execute(
            {
                "task_id": "d-1",
                "type": "analyze_response_decision",
                "entity_id": "node-1",
                "entity_type": "machine",
                "risk_level": 5,
                "asset_criticality": 0.9,
                "meta_decision": {
                    "trusted_output": {
                        "conflict_score": 0.72,
                        "deep_analysis_triggered": True,
                    },
                    "deep_analysis_requests": [
                        {
                            "event_id": "evt-1",
                            "entity_id": "node-1",
                            "agent_id": "decision",
                            "reasons": ["agent_conflict", "critical_asset"],
                            "deadline_ms": 150,
                        }
                    ],
                },
            }
        )
        assert result.success is True
        assert "explanation" in result.output
        assert "hypotheses" in result.output
        assert "counterfactuals" in result.output
        assert "feature_importance" in result.output
        assert "confidence_interval" in result.output
        assert result.output["feature_importance"]["conflict_score"] == 0.72
        assert result.actions_taken[-1]["action"] == "deep_analysis"

    asyncio.run(run())


def test_decision_agent_keeps_committee_path_without_meta_decision() -> None:
    async def run() -> None:
        agent = DecisionAgent()
        agent.mcp = FakeMCP()
        result = await agent.execute(
            {
                "task_id": "d-2",
                "type": "explain_human_decision",
                "entity_id": "node-2",
                "entity_type": "machine",
            }
        )
        assert result.success is True
        assert "committee" in result.output
        assert result.model_used == "committee"

    asyncio.run(run())
