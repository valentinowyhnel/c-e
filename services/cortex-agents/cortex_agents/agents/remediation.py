from __future__ import annotations

import json
import sys
from pathlib import Path

from ..base import AgentResult, CortexBaseAgent

ROOT = Path(__file__).resolve().parents[4] / "shared" / "cortex-core"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_core.contracts import CapabilityMaturity, ExecutionMode  # noqa: E402


class RemediationAgent(CortexBaseAgent):
    def __init__(self):
        super().__init__(agent_id="remediation")

    async def execute(self, task: dict):
        handlers = {
            "prepare_issue_sot": self._prepare_issue_sot,
            "execute_issue_sot": self._execute_issue_sot,
            "prepare_quarantine": self._prepare_quarantine,
            "execute_quarantine": self._execute_quarantine,
            "prepare_irreversible_containment": self._prepare_irreversible_containment,
            "execute_irreversible_containment": self._execute_irreversible_containment,
        }
        handler = handlers[task["type"]]
        return await handler(task)

    async def _prepare_issue_sot(self, task):
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output={
                "plan_type": "issue_sot",
                "entity_id": task["entity_id"],
                "reasons": task.get("reasons", []),
                "approval_required": False,
                "rollback_possible": True,
            },
            reasoning=f"SOT plan prepared for {task['entity_id']}",
            actions_taken=[{"action": "prepare_issue_sot"}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _execute_issue_sot(self, task):
        async with self.mcp as mcp:
            result = await mcp.call_tool(
                "issue_sot",
                {
                    "entity_id": task["entity_id"],
                    "entity_type": task.get("entity_type", "machine"),
                    "reasons": task.get("reasons", []),
                    "score": task.get("score", 50.0),
                },
            )
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output={"sot": result, "entity_id": task["entity_id"]},
            reasoning=f"SOT issued for {task['entity_id']}",
            actions_taken=[{"action": "issue_sot"}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _prepare_quarantine(self, task):
        async with self.mcp as mcp:
            blast_tool = "bh_get_blast_radius" if task.get("entity_type") in {"user", "group", "computer", "ad_object"} else "get_blast_radius"
            blast = await mcp.call_tool(blast_tool, {"entity_id": task["entity_id"]})
            privilege_context = None
            if task.get("entity_type") in {"user", "group", "computer", "ad_object"}:
                privilege_context = await mcp.call_tool(
                    "bh_answer_privilege_question",
                    {
                        "subject": task["entity_id"],
                        "question": "What privileged paths and tier 0 resources are exposed by this entity?",
                    },
                )
            decision = await mcp.call_tool(
                "decision_analyze_response",
                {
                    "task_id": task["task_id"],
                    "entity_id": task["entity_id"],
                    "entity_type": task.get("entity_type", "machine"),
                    "candidate_action": "quarantine",
                    "blast_radius": blast.get("result", {}),
                    "privilege_context": privilege_context.get("result", {}) if privilege_context else None,
                },
            )
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output={
                "plan_type": "quarantine",
                "blast_radius": blast.get("result", {}),
                "privilege_context": privilege_context.get("result", {}) if privilege_context else None,
                "decision": decision.get("result", {}),
                "approval_required": True,
                "rollback_possible": True,
            },
            reasoning=f"Quarantine plan ready for {task['entity_id']}",
            actions_taken=[],
            requires_approval=True,
            approval_payload={
                "action": "quarantine",
                "entity_id": task["entity_id"],
                "blast_radius": blast.get("result", {}),
                "privilege_context": privilege_context.get("result", {}) if privilege_context else None,
                "decision": decision.get("result", {}),
                "risk_level": 4,
            },
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.BETA.value,
        )

    async def _execute_quarantine(self, task):
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=False,
            output={"blocked": True, "reason": "execute_quarantine requires host-specific executor and approval handoff"},
            reasoning="Execution path intentionally blocked until dedicated executor is policy-bound.",
            actions_taken=[],
            requires_approval=True,
            approval_payload={"action": "execute_quarantine", "entity_id": task["entity_id"]},
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.EXPERIMENTAL.value,
        )

    async def _prepare_irreversible_containment(self, task):
        async with self.mcp as mcp:
            blast_tool = "bh_get_blast_radius" if task.get("entity_type") in {"user", "group", "computer", "ad_object"} else "get_blast_radius"
            blast = await mcp.call_tool(blast_tool, {"entity_id": task["entity_id"]})
            forensic = await mcp.call_tool("forensic_preserve", {"entity_id": task["entity_id"]})
            privilege_path = None
            if task.get("entity_type") in {"user", "group", "computer", "ad_object"}:
                privilege_path = await mcp.call_tool(
                    "bh_get_attack_path",
                    {
                        "source": task["entity_id"],
                        "target": task.get("target", "tier0"),
                    },
                )
            analysis = await mcp.complete(
                task="explain apoptosis plan for human approval",
                input_data=json.dumps(
                    {
                        "entity_id": task["entity_id"],
                        "trust_score": task.get("trust_score", 0),
                        "trigger_signals": task.get("trigger_signals", []),
                        "blast_radius": blast.get("result", {}),
                        "privilege_path": privilege_path.get("result", {}) if privilege_path else None,
                    }
                ),
                system_prompt=(
                    "You are a senior security analyst. Explain clearly for a human operator "
                    "what happened, what will be done, what is at risk, and what cannot be undone."
                ),
                max_tokens=600,
                temperature=0.2,
            )
            decision = await mcp.call_tool(
                "decision_analyze_response",
                {
                    "task_id": task["task_id"],
                    "entity_id": task["entity_id"],
                    "entity_type": task.get("entity_type", "machine"),
                    "candidate_action": "trigger_apoptosis",
                    "blast_radius": blast.get("result", {}),
                    "privilege_path": privilege_path.get("result", {}) if privilege_path else None,
                    "analysis": analysis["output"],
                },
            )
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output={
                "plan_type": "irreversible_containment",
                "blast_radius": blast.get("result", {}),
                "forensic": forensic,
                "privilege_path": privilege_path.get("result", {}) if privilege_path else None,
                "explanation": analysis["output"],
                "decision": decision.get("result", {}),
                "forensic_required": True,
                "rollback_possible": False,
            },
            reasoning=analysis["output"][:300],
            actions_taken=[{"action": "forensic_preserve"}],
            requires_approval=True,
            approval_payload={
                "action": "prepare_irreversible_containment",
                "entity_id": task["entity_id"],
                "trust_score": task.get("trust_score", 0),
                "blast_radius": blast.get("result", {}),
                "privilege_path": privilege_path.get("result", {}) if privilege_path else None,
                "decision": decision.get("result", {}),
                "risk_level": 5,
                "explanation": analysis["output"],
            },
            duration_ms=0,
            tokens_used=0,
            model_used=analysis.get("model_used", ""),
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.EXPERIMENTAL.value,
        )

    async def _execute_irreversible_containment(self, task):
        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=False,
            output={"blocked": True, "reason": "irreversible containment remains policy-blocked in current maturity level"},
            reasoning="Irreversible action denied by design at current maturity.",
            actions_taken=[],
            requires_approval=True,
            approval_payload={"action": "execute_irreversible_containment", "entity_id": task["entity_id"]},
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.EXPERIMENTAL.value,
        )
