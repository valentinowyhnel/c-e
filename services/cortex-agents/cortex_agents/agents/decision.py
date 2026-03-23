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

    @staticmethod
    def _deep_analysis_requested(task: dict) -> bool:
        meta_decision = task.get("meta_decision", {})
        trusted_output = meta_decision.get("trusted_output", {}) if isinstance(meta_decision, dict) else {}
        deep_requests = task.get("deep_analysis_request") or meta_decision.get("deep_analysis_requests", [])
        return bool(trusted_output.get("deep_analysis_triggered") or deep_requests)

    @staticmethod
    def _deep_analysis_payload(task: dict) -> dict:
        meta_decision = task.get("meta_decision", {}) if isinstance(task.get("meta_decision", {}), dict) else {}
        request = task.get("deep_analysis_request", {})
        trusted_output = meta_decision.get("trusted_output", {})
        return {
            "task": task,
            "meta_decision": meta_decision,
            "deep_analysis_request": request,
            "trusted_output": trusted_output,
        }

    async def _run_deep_analysis(self, task_name: str, payload: dict, system_prompt: str) -> dict:
        async with self.mcp as mcp:
            explanation = await mcp.complete(
                task=task_name,
                input_data=json.dumps(payload),
                system_prompt=system_prompt,
                max_tokens=900,
                temperature=0.1,
                params={"force_model": "claude"},
            )
            hypotheses = await mcp.complete(
                task=f"{task_name} hypotheses",
                input_data=json.dumps(payload),
                system_prompt=(
                    "List the most plausible hypotheses, competing explanations, and failure modes. "
                    "Return concise analytical prose."
                ),
                max_tokens=600,
                temperature=0.2,
                params={"force_model": "openai-gpt5"},
            )
            counterfactuals = await mcp.complete(
                task=f"{task_name} counterfactuals",
                input_data=json.dumps(payload),
                system_prompt=(
                    "Provide counterfactuals that would change the decision and name the missing evidence."
                ),
                max_tokens=500,
                temperature=0.2,
                params={"force_model": "openai-gpt45"},
            )
        feature_importance = {
            "risk_level": float(payload["task"].get("risk_level", 0)) / 5.0 if payload["task"].get("risk_level") is not None else 0.0,
            "conflict_score": float(payload.get("trusted_output", {}).get("conflict_score", 0.0)),
            "novelty_score": float(payload["task"].get("novelty_score", 0.0)),
            "asset_criticality": float(payload["task"].get("asset_criticality", 0.0)),
        }
        confidence_center = max(0.1, min(0.95, 0.55 + 0.25 * feature_importance["conflict_score"] + 0.10 * feature_importance["asset_criticality"]))
        confidence_interval = [max(0.0, round(confidence_center - 0.15, 3)), min(1.0, round(confidence_center + 0.1, 3))]
        return {
            "explanation": explanation["output"],
            "hypotheses": [hypotheses["output"]],
            "counterfactuals": [counterfactuals["output"]],
            "feature_importance": feature_importance,
            "confidence_interval": confidence_interval,
            "model_used": "deep_analysis_committee",
        }

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
        if self._deep_analysis_requested(task):
            analysis = await self._run_deep_analysis(
                "deep response decision analysis",
                self._deep_analysis_payload(task),
                system_prompt=(
                    "You are a senior security response analyst. Produce a deep analysis with explanation, "
                    "hypotheses, counterfactuals, feature importance, and calibrated confidence interval."
                ),
            )
            return AgentResult(
                task_id=task["task_id"],
                agent_id=self.agent_id,
                success=True,
                output=analysis,
                reasoning=str(analysis["explanation"])[:400],
                actions_taken=[{"action": "analyze_response_decision"}, {"action": "deep_analysis"}],
                requires_approval=True,
                approval_payload={"deep_analysis": analysis},
                duration_ms=0,
                tokens_used=0,
                model_used=analysis["model_used"],
                execution_mode=ExecutionMode.PREPARE.value,
                capability_maturity=CapabilityMaturity.BETA.value,
            )
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
        if self._deep_analysis_requested(task):
            analysis = await self._run_deep_analysis(
                "deep human approval explanation",
                self._deep_analysis_payload(task),
                system_prompt=(
                    "You are a human-facing decision explainer. Provide a deep explanation for approval, "
                    "including alternatives and uncertainty."
                ),
            )
            return AgentResult(
                task_id=task["task_id"],
                agent_id=self.agent_id,
                success=True,
                output=analysis,
                reasoning=str(analysis["explanation"])[:400],
                actions_taken=[{"action": "explain_human_decision"}, {"action": "deep_analysis"}],
                requires_approval=False,
                approval_payload=None,
                duration_ms=0,
                tokens_used=0,
                model_used=analysis["model_used"],
                execution_mode=ExecutionMode.PREPARE.value,
                capability_maturity=CapabilityMaturity.BETA.value,
            )
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
