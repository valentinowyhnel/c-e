from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
for root in (ROOT, CORE_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from cortex_agents.agents.remediation import RemediationAgent


class FakeMCP:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def call_tool(self, tool_name: str, params: dict):
        self.calls.append((tool_name, params))
        if tool_name in {"get_blast_radius", "bh_get_blast_radius"}:
            return {"result": {"reachable_entities": ["db-1"], "score": 32}}
        if tool_name == "bh_answer_privilege_question":
            return {"result": {"paths": ["user->group->tier0"], "tier0": True}}
        if tool_name == "forensic_preserve":
            return {"result": {"preserved": True}}
        if tool_name == "bh_get_attack_path":
            return {"result": {"has_path": True, "path_count": 1}}
        if tool_name == "decision_analyze_response":
            return {"result": {"committee": "ok", "advisory_only": True}}
        return {"result": {}}

    async def complete(self, **kwargs):
        return {"output": "Human explanation", "model_used": "claude"}


def test_prepare_quarantine_requires_approval() -> None:
    async def run() -> None:
        agent = RemediationAgent()
        agent.mcp = FakeMCP()

        result = await agent.execute(
            {
                "task_id": "q-1",
                "type": "prepare_quarantine",
                "entity_id": "machine-1",
                "entity_type": "machine",
            }
        )

        assert result.success is True
        assert result.requires_approval is True
        assert result.execution_mode == "prepare"
        assert result.output["plan_type"] == "quarantine"

    asyncio.run(run())


def test_prepare_irreversible_contains_forensic_prerequisite() -> None:
    async def run() -> None:
        agent = RemediationAgent()
        fake_mcp = FakeMCP()
        agent.mcp = fake_mcp

        result = await agent.execute(
            {
                "task_id": "i-1",
                "type": "prepare_irreversible_containment",
                "entity_id": "user:alice",
                "entity_type": "user",
                "trust_score": 5,
                "trigger_signals": ["cred_dump", "tamper"],
            }
        )

        assert result.success is True
        assert result.requires_approval is True
        assert result.execution_mode == "prepare"
        assert result.output["forensic_required"] is True
        assert any(tool == "forensic_preserve" for tool, _ in fake_mcp.calls)

    asyncio.run(run())


def test_execute_irreversible_remains_blocked() -> None:
    async def run() -> None:
        agent = RemediationAgent()
        agent.mcp = FakeMCP()

        result = await agent.execute(
            {
                "task_id": "x-1",
                "type": "execute_irreversible_containment",
                "entity_id": "user:alice",
            }
        )

        assert result.success is False
        assert result.requires_approval is True
        assert result.capability_maturity == "experimental"

    asyncio.run(run())
