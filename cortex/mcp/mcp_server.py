from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from cortex.llm import LLMGateway

from .mcp_context_builder import MCPContextBuilder
from .mcp_output_filter import MCPOutputFilter
from .mcp_policy_guard import MCPPolicyGuard
from .mcp_router import MCPRouter
from .mcp_tool_registry import MCPToolRegistry


class VLLMCallable(Protocol):
    def __call__(self, route_model: str, context: dict[str, object], timeout_ms: int) -> dict[str, object]:
        ...


@dataclass
class MCPAnalysisResult:
    structured_output: dict[str, object]
    audit_log: dict[str, object]
    degraded_mode: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "structured_output": dict(self.structured_output),
            "audit_log": dict(self.audit_log),
            "degraded_mode": self.degraded_mode,
        }


class MCPServer:
    def __init__(
        self,
        *,
        context_builder: MCPContextBuilder | None = None,
        router: MCPRouter | None = None,
        policy_guard: MCPPolicyGuard | None = None,
        tool_registry: MCPToolRegistry | None = None,
        output_filter: MCPOutputFilter | None = None,
        vllm_callable: VLLMCallable | None = None,
        llm_gateway: LLMGateway | None = None,
        timeout_ms: int = 150,
    ) -> None:
        self.context_builder = context_builder or MCPContextBuilder()
        self.router = router or MCPRouter()
        self.policy_guard = policy_guard or MCPPolicyGuard()
        self.tool_registry = tool_registry or MCPToolRegistry()
        self.output_filter = output_filter or MCPOutputFilter()
        self.vllm_callable = vllm_callable or self._default_vllm_callable
        self.llm_gateway = llm_gateway or LLMGateway(vllm_callable=self.vllm_callable)
        self.timeout_ms = timeout_ms

    def _default_vllm_callable(
        self,
        route_model: str,
        context: dict[str, object],
        timeout_ms: int,
    ) -> dict[str, object]:
        payload = dict(context.get("payload", {}))
        event = dict(payload.get("event", {}))
        messages = list(payload.get("agent_messages", []))
        trust_scores = dict(payload.get("trust_scores", {}))
        conflict_score = float(payload.get("conflict_score", 0.0))
        top_agents = sorted(trust_scores.items(), key=lambda item: float(item[1]), reverse=True)[:3]

        return {
            "hypotheses": [
                f"{event.get('scenario', 'unknown_scenario')} may be a staged multi-step attack path.",
                "Agent disagreement may be driven by partial visibility across graph, endpoint, and trust signals.",
                "The event may be a variant of a known technique with atypical timing or target selection.",
            ],
            "explanation": (
                f"Advisory analysis from {route_model} under timeout {timeout_ms}ms. "
                f"Conflict={conflict_score:.3f}. "
                f"Most trusted agents={', '.join(agent for agent, _score in top_agents) or 'none'}."
            ),
            "agent_comparison": {
                str(message.get("agent_id", f"agent-{index}")): (
                    f"risk_signal={float(message.get('risk_signal', 0.0)):.3f}; "
                    f"uncertainty={float(message.get('uncertainty', 0.0)):.3f}; "
                    f"reasoning_quality={float(message.get('reasoning_quality', 0.0)):.3f}"
                )
                for index, message in enumerate(messages)
            },
            "suggestions": [
                "Request bounded deep analysis from the highest-trust conflicting agents.",
                "Ask Sentinel RL to validate whether telemetry gaps explain the disagreement.",
                "Re-check graph and temporal context before any irreversible containment proposal.",
            ],
            "final_decision": "forbidden",
        }

    @staticmethod
    def _blocked_output(explanation: str) -> dict[str, object]:
        return {
            "hypotheses": [],
            "explanation": explanation,
            "agent_comparison": {},
            "suggestions": [],
            "advisory_only": True,
        }

    def analyze(
        self,
        *,
        event: dict[str, object],
        agent_messages: list[dict[str, object]],
        trust_scores: dict[str, float],
        conflict_score: float,
        deep_analysis_reasons: list[str],
        memory_context: dict[str, object] | None = None,
    ) -> MCPAnalysisResult:
        started = time.monotonic()
        context = self.context_builder.build(
            event=event,
            agent_messages=agent_messages,
            trust_scores=trust_scores,
            conflict_score=conflict_score,
            deep_analysis_reasons=deep_analysis_reasons,
            memory_context=memory_context,
        )
        request = context.to_dict()
        guard = self.policy_guard.validate_request(request)
        audit_log: dict[str, object] = {
            "event_id": context.event_id,
            "task": context.task,
            "origin": request["payload"].get("origin"),
            "allowed": guard.allowed,
            "guard_reasons": guard.reasons,
            "tools": self.tool_registry.list_tools(),
            "audit_required": True,
            "sentinel_validation_required": True,
        }
        if not guard.allowed:
            audit_log["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            return MCPAnalysisResult(
                structured_output=self._blocked_output("mcp_policy_guard_blocked"),
                audit_log=audit_log,
                degraded_mode=True,
            )

        route = self.router.route(request)
        effective_timeout_ms = min(self.timeout_ms, route.timeout_ms)
        audit_log["route"] = route.to_dict()
        audit_log["requested_timeout_ms"] = self.timeout_ms
        audit_log["effective_timeout_ms"] = effective_timeout_ms

        try:
            gateway_response = self.llm_gateway.invoke(
                route_reason=route.reason,
                route_model=route.model,
                context=request,
                timeout_ms=effective_timeout_ms,
            )
            raw_output = gateway_response.raw_output
        except Exception as exc:
            audit_log["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            audit_log["error"] = f"vllm_call_failed:{exc}"
            return MCPAnalysisResult(
                structured_output=self._blocked_output("mcp_vllm_call_failed"),
                audit_log=audit_log,
                degraded_mode=True,
            )

        filtered = self.output_filter.filter(raw_output)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        degraded = elapsed_ms > effective_timeout_ms
        audit_log["elapsed_ms"] = elapsed_ms
        audit_log["discarded_fields"] = filtered.discarded_fields
        audit_log["output_schema"] = "json"
        audit_log["advisory_only"] = True
        audit_log["llm_profile"] = gateway_response.profile.to_dict()
        audit_log["llm_model_metadata"] = gateway_response.model_metadata
        if degraded:
            audit_log["timeout_exceeded"] = True
            return MCPAnalysisResult(
                structured_output=self._blocked_output("mcp_timeout_degraded"),
                audit_log=audit_log,
                degraded_mode=True,
            )
        return MCPAnalysisResult(
            structured_output=filtered.to_dict() | {"advisory_only": True},
            audit_log=audit_log,
            degraded_mode=False,
        )
