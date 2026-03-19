from __future__ import annotations

import json
import sys
from pathlib import Path

from ..base import AgentResult, CortexBaseAgent

ROOT = Path(__file__).resolve().parents[4] / "shared" / "cortex-core"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_core.contracts import CapabilityMaturity, ExecutionMode  # noqa: E402


class DecisionAgent(CortexBaseAgent):
    def __init__(self):
        super().__init__(agent_id="decision")

    async def execute(self, task: dict):
        handlers = {
            "assess_privilege_change": self._assess_privilege_change,
            "analyze_response_decision": self._analyze_response_decision,
            "explain_human_decision": self._explain_human_decision,
        }
        handler = handlers.get(task["type"])
        if handler is None:
            raise RuntimeError(f"unknown decision task: {task['type']}")
        return await handler(task)

    async def _committee(self, task_name: str, payload: dict, system_prompt: str) -> dict:
        analyses = {}
        consulted_models: list[str] = []
        async with self.mcp as mcp:
            for force_model in ("claude", "openai-gpt5", "openai-gpt45"):
                analyses[force_model] = await mcp.complete(
                    task=task_name,
                    input_data=json.dumps(payload),
                    system_prompt=system_prompt,
                    max_tokens=900,
                    temperature=0.2,
                    params={"force_model": force_model},
                )
                consulted_models.append(force_model)
            synthesis = await mcp.complete(
                task="high risk decision synthesis",
                input_data=json.dumps(
                    {
                        "task": task_name,
                        "payload": payload,
                        "committee": {
                            model: result["output"]
                            for model, result in analyses.items()
                        },
                    }
                ),
                system_prompt=(
                    "You are the final decision arbiter for Cortex. "
                    "Synthesize the committee analyses into one decision, "
                    "state confidence, approval need, and concrete rationale."
                ),
                max_tokens=1000,
                temperature=0.1,
                params={"force_model": "claude"},
            )
        return {
            "committee": analyses,
            "synthesis": synthesis,
            "consulted_models": consulted_models,
            "advisory_only": True,
            "authority_boundary": "policy_and_approval_required_for_execution",
        }

    async def _assess_privilege_change(self, task: dict) -> AgentResult:
        async with self.mcp as mcp:
            path = await mcp.call_tool(
                "bh_get_attack_path",
                {"source": task["source"], "target": task.get("target", "tier0")},
            )
            blast = await mcp.call_tool(
                "bh_get_blast_radius",
                {"entity_id": task["source"]},
            )
            validation = await mcp.call_tool(
                "ad_validate_group_membership",
                {
                    "account_sid": task.get("account_sid", task["source"]),
                    "group_dn": task["group_dn"],
                },
            )
        committee = await self._committee(
            "high risk decision",
            {
                "requested_change": task,
                "attack_path": path["result"],
                "blast_radius": blast["result"],
                "validation": validation["result"],
            },
            system_prompt=(
                "You are a privileged access decision engine. "
                "Decide whether the privilege change should be allowed, "
                "require approval, or be denied."
            ),
        )
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output=committee,
            reasoning=committee["synthesis"]["output"][:400],
            actions_taken=[{"action": "assess_privilege_change"}],
            requires_approval=True,
            approval_payload=committee["synthesis"],
            duration_ms=0,
            tokens_used=0,
            model_used="committee",
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.BETA.value,
        )

    async def _analyze_response_decision(self, task: dict) -> AgentResult:
        committee = await self._committee(
            "high risk decision",
            task,
            system_prompt=(
                "You are a security response decision engine. "
                "Assess containment, quarantine, apoptosis, and approval needs."
            ),
        )
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output=committee,
            reasoning=committee["synthesis"]["output"][:400],
            actions_taken=[{"action": "analyze_response_decision"}],
            requires_approval=True,
            approval_payload=committee["synthesis"],
            duration_ms=0,
            tokens_used=0,
            model_used="committee",
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.BETA.value,
        )

    async def _explain_human_decision(self, task: dict) -> AgentResult:
        committee = await self._committee(
            "human explanation",
            task,
            system_prompt=(
                "You are a human-facing decision explainer. "
                "Write a crisp approval memo in plain language."
            ),
        )
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output=committee,
            reasoning=committee["synthesis"]["output"][:400],
            actions_taken=[{"action": "explain_human_decision"}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            model_used="committee",
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.BETA.value,
        )
