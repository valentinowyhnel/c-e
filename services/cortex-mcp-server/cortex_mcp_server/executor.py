from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from .config import MCPServerConfig
from .router import ModelID, RoutingDecision

from cortex_core.contracts import (  # noqa: E402
    ActionClass,
    CapabilityMaturity,
    DependencyHealthSnapshot,
    DependencyState,
    ExecutionDecision,
    ExecutionGuardrails,
    RiskEnvelope,
)
from cortex_core.messages import AgentTask  # noqa: E402
from cortex_core.maturity import CAPABILITY_REGISTRY  # noqa: E402
from cortex_core.meta_decision import MetaDecisionEvent  # noqa: E402
from cortex_policy_engine.engine import PolicyEngine  # noqa: E402


MODEL_ENV_MAP = {
    ModelID.PHI3_MINI: ("PHI3_ENDPOINT", "PHI3_API_KEY"),
    ModelID.MISTRAL_7B: ("MISTRAL_ENDPOINT", "MISTRAL_API_KEY"),
    ModelID.LLAMA3_8B: ("LLAMA3_ENDPOINT", "LLAMA3_API_KEY"),
    ModelID.CODELLAMA_13B: ("CODELLAMA_ENDPOINT", "CODELLAMA_API_KEY"),
}

_http_pools: dict[str, httpx.AsyncClient] = {}
_nats_client = None

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "ad_validate_group_membership": {
        "category": "ad_precheck",
        "risk_level": 2,
        "check": "bloodhound_group_membership_risk",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "validate_group_membership",
        "action_class": ActionClass.READ_ONLY,
        "capability": "ad_read_validations",
    },
    "ad_validate_service_account": {
        "category": "ad_precheck",
        "risk_level": 3,
        "check": "kerberos_spn_and_delegation_validation",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "validate_service_account",
        "action_class": ActionClass.READ_ONLY,
        "capability": "ad_read_validations",
    },
    "ad_run_drift_scan": {
        "category": "ad_drift",
        "risk_level": 2,
        "check": "snapshot_and_drift_scan",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "run_drift_scan",
        "action_class": ActionClass.READ_ONLY,
        "capability": "ad_read_validations",
    },
    "ad_restore_deleted": {
        "category": "ad_recovery",
        "risk_level": 4,
        "check": "recycle_bin_restore",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "restore_deleted",
        "action_class": ActionClass.EXECUTE_WITH_APPROVAL,
        "capability": "ad_destructive_writes",
    },
    "ad_get_object_acl": {
        "category": "ad_read",
        "risk_level": 1,
        "check": "security_descriptor_read",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "get_object_acl",
        "action_class": ActionClass.READ_ONLY,
        "capability": "ad_read_validations",
    },
    "ad_get_deleted_objects": {
        "category": "ad_read",
        "risk_level": 1,
        "check": "show_deleted_search",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "get_deleted_objects",
        "action_class": ActionClass.READ_ONLY,
        "capability": "ad_read_validations",
    },
    "ad_dirsync_changes": {
        "category": "ad_monitoring",
        "risk_level": 2,
        "check": "dirsync_incremental_changes",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "dirsync_changes",
        "action_class": ActionClass.READ_ONLY,
        "capability": "ad_read_validations",
    },
    "bh_get_attack_path": {
        "category": "bloodhound_analysis",
        "risk_level": 2,
        "check": "privilege_path_lookup",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "get_attack_path",
        "action_class": ActionClass.READ_ONLY,
        "capability": "bloodhound_exposure_analysis",
    },
    "bh_get_blast_radius": {
        "category": "bloodhound_analysis",
        "risk_level": 2,
        "check": "resource_exposure_lookup",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "get_blast_radius",
        "action_class": ActionClass.READ_ONLY,
        "capability": "bloodhound_exposure_analysis",
    },
    "bh_answer_privilege_question": {
        "category": "bloodhound_analysis",
        "risk_level": 2,
        "check": "privilege_question_answering",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "answer_privilege_question",
        "action_class": ActionClass.ADVISORY,
        "capability": "bloodhound_exposure_analysis",
    },
    "bh_visualize_exposure": {
        "category": "bloodhound_visualization",
        "risk_level": 1,
        "check": "exposure_graph_projection",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "visualize_exposure",
        "action_class": ActionClass.READ_ONLY,
        "capability": "bloodhound_exposure_analysis",
    },
    "bh_get_tier0_assets": {
        "category": "bloodhound_analysis",
        "risk_level": 1,
        "check": "tier0_inventory",
        "subject": "cortex.agents.tasks.ad",
        "task_type": "get_tier0_assets",
        "action_class": ActionClass.READ_ONLY,
        "capability": "bloodhound_exposure_analysis",
    },
    "decision_assess_privilege_change": {
        "category": "decision",
        "risk_level": 4,
        "check": "privilege_change_decision_committee",
        "subject": "cortex.agents.tasks.decision",
        "task_type": "assess_privilege_change",
        "action_class": ActionClass.ADVISORY,
        "capability": "decision_committee",
    },
    "decision_analyze_response": {
        "category": "decision",
        "risk_level": 4,
        "check": "response_decision_committee",
        "subject": "cortex.agents.tasks.decision",
        "task_type": "analyze_response_decision",
        "action_class": ActionClass.ADVISORY,
        "capability": "decision_committee",
    },
    "decision_explain_human": {
        "category": "decision",
        "risk_level": 3,
        "check": "human_explanation_committee",
        "subject": "cortex.agents.tasks.decision",
        "task_type": "explain_human_decision",
        "action_class": ActionClass.ADVISORY,
        "capability": "decision_committee",
    },
}


def get_http_client(model_id: str) -> httpx.AsyncClient:
    if model_id not in _http_pools:
        is_cpu = model_id in {"phi3-mini", "mistral-7b"}
        _http_pools[model_id] = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=20 if is_cpu else 10,
                max_keepalive_connections=10 if is_cpu else 5,
                keepalive_expiry=30.0,
            ),
            timeout=None,
        )
    return _http_pools[model_id]


class MCPExecutor:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.policy = PolicyEngine()

    async def execute_with_fallback(
        self,
        decision: RoutingDecision,
        messages: list[dict[str, str]],
        generation_params: dict[str, Any],
        agent_id: str,
        audit: Any | None = None,
    ) -> dict[str, Any]:
        primary = decision.primary_model
        fallback = decision.fallback_model
        try:
            result = await self._call_model(primary, messages, generation_params)
            return {
                "content": result,
                "model_used": primary.value,
                "was_fallback": False,
                "agent_id": agent_id,
            }
        except Exception:
            if fallback != primary:
                result = await self._call_model(fallback, messages, generation_params)
                return {
                    "content": result,
                    "model_used": fallback.value,
                    "was_fallback": True,
                    "agent_id": agent_id,
                }
            raise

    async def execute_tool(self, tool: str, params: dict[str, Any], agent_id: str) -> dict[str, Any]:
        if tool in TOOL_SPECS:
            spec = TOOL_SPECS[tool]
            policy_decision = self._evaluate_tool_policy(tool, spec, params)
            if policy_decision.decision in {
                ExecutionDecision.DENIED,
                ExecutionDecision.BLOCKED_DUE_TO_DEGRADED_MODE,
            }:
                return {
                    "tool": tool,
                    "agent_id": agent_id,
                    "params": params,
                    "category": spec["category"],
                    "risk_level": spec["risk_level"],
                    "decision_right": spec["action_class"].value,
                    "policy_decision": policy_decision.model_dump(),
                    "status": "blocked",
                }
            result = await self._dispatch_agent_tool(tool, params, spec)
            return {
                "tool": tool,
                "agent_id": agent_id,
                "params": params,
                "category": spec["category"],
                "risk_level": spec["risk_level"],
                "check": spec["check"],
                "decision_right": spec["action_class"].value,
                "policy_decision": policy_decision.model_dump(),
                "status": "completed" if result.get("success") else "failed",
                "task_subject": spec["subject"],
                "agent_result": result,
            }
        if tool == "issue_sot":
            result = await self._call_trust_engine_sot(params)
            return {
                "tool": tool,
                "agent_id": agent_id,
                "params": params,
                "category": "response",
                "risk_level": 4,
                "decision_right": ActionClass.EXECUTE_WITH_APPROVAL.value,
                "status": "completed",
                "result": result,
            }
        if tool == "forensic_preserve":
            return {
                "tool": tool,
                "agent_id": agent_id,
                "params": params,
                "category": "response",
                "risk_level": 4,
                "decision_right": ActionClass.PREPARE_ONLY.value,
                "status": "planned",
                "result": {
                    "entity_id": params.get("entity_id"),
                    "preservation_scope": "memory,disk,process_tree,network_context",
                    "next_step": "handoff_to_human_or_forensic_worker",
                },
            }
        if tool == "get_blast_radius":
            return {
                "tool": tool,
                "agent_id": agent_id,
                "params": params,
                "category": "analysis",
                "risk_level": 2,
                "decision_right": ActionClass.READ_ONLY.value,
                "status": "completed",
                "result": {
                    "entity_id": params.get("entity_id"),
                    "summary": "generic_blast_radius",
                    "reachable_entities": [],
                },
            }
        raise ValueError(f"Unsupported tool: {tool}")

    def _evaluate_tool_policy(self, tool: str, spec: dict[str, Any], params: dict[str, Any]):
        capability_name = spec["capability"]
        capability = CAPABILITY_REGISTRY[capability_name]
        envelope = RiskEnvelope(
            entity_id=str(params.get("entity_id") or params.get("account_dn") or "unknown"),
            entity_type=str(params.get("entity_type") or "unknown"),
            action=tool,
            action_class=spec["action_class"],
            trust_score=float(params.get("trust_score", 50.0)),
            threat_level=int(params.get("risk_level", spec["risk_level"])),
            evidence_count=int(params.get("evidence_count", 0)),
            strong_signal_count=int(params.get("strong_signal_count", 0)),
            distinct_sources=int(params.get("distinct_sources", 0)),
            blast_radius=int(params.get("blast_radius", 0)),
            crown_jewels_exposed=bool(params.get("crown_jewels_exposed", False)),
            criticality=str(params.get("criticality", "normal")),
            scopes=list(params.get("scopes", ["admin:write"])),
            environment=os.getenv("CORTEX_ENVIRONMENT", "preprod"),
            dry_run=bool(params.get("dry_run", False)),
            maturity=capability.maturity,
            dependencies=DependencyHealthSnapshot(
                nats=DependencyState.HEALTHY,
                approval=DependencyState.HEALTHY,
                sentinel=DependencyState.HEALTHY,
                vault=DependencyState.HEALTHY,
                neo4j=DependencyState.HEALTHY,
                bloodhound=DependencyState.HEALTHY,
                external_llm=DependencyState.HEALTHY,
            ),
        )
        guardrails = ExecutionGuardrails(
            action_class=spec["action_class"],
            approval_required=spec["action_class"] == ActionClass.EXECUTE_WITH_APPROVAL,
            forensic_required=spec["action_class"] == ActionClass.IRREVERSIBLE,
            min_sources=2 if spec["action_class"] == ActionClass.IRREVERSIBLE else 1,
            block_if_maturity_below=CapabilityMaturity.PREPROD_READY,
        )
        return self.policy.evaluate(envelope, guardrails, capability_name)

    async def _call_model(
        self,
        model_id: ModelID,
        messages: list[dict[str, str]],
        params: dict[str, Any],
    ) -> str:
        if model_id == ModelID.CLAUDE:
            return await self._call_claude(messages, params)
        if model_id in {ModelID.OPENAI_GPT5, ModelID.OPENAI_GPT45}:
            return await self._call_openai(model_id, messages, params)
        return await self.call_vllm_model(model_id, messages, params)

    async def call_vllm_model(
        self,
        model_id: ModelID,
        messages: list[dict[str, str]],
        params: dict[str, Any],
    ) -> str:
        endpoint, api_key = self._endpoint_and_key(model_id)
        client = get_http_client(model_id.value)
        payload: dict[str, Any] = {
            "model": model_id.value,
            "messages": messages,
            "max_tokens": params.get("max_tokens", 1000),
            "temperature": params.get("temperature", 0.3),
            "stream": False,
        }
        if params.get("stop"):
            payload["stop"] = params["stop"]
        if params.get("expected_format") == "json":
            payload["response_format"] = {"type": "json_object"}
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = await asyncio.wait_for(
            client.post(f"{endpoint}/v1/chat/completions", json=payload, headers=headers),
            timeout=float(params.get("timeout", 30.0)),
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def _call_claude(self, messages: list[dict[str, str]], params: dict[str, Any]) -> str:
        api_key = self.config.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            user_prompt = next((message["content"] for message in reversed(messages) if message["role"] == "user"), "")
            return (
                "Claude unavailable in local mode. "
                f"Fallback analysis for request: {user_prompt[:200]}"
            )
        system_prompt = next((message["content"] for message in messages if message["role"] == "system"), "")
        user_messages = [message for message in messages if message["role"] != "system"]
        response = await httpx.AsyncClient(timeout=30.0).post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.config.claude_model,
                "max_tokens": params.get("max_tokens", 1000),
                "system": system_prompt,
                "messages": user_messages,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    async def _call_openai(self, model_id: ModelID, messages: list[dict[str, str]], params: dict[str, Any]) -> str:
        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            user_prompt = next((message["content"] for message in reversed(messages) if message["role"] == "user"), "")
            return (
                f"{model_id.value} unavailable in local mode. "
                f"Fallback analysis for request: {user_prompt[:200]}"
            )
        model_name = self.config.openai_gpt5_model if model_id == ModelID.OPENAI_GPT5 else (
            self.config.openai_gpt45_model or self.config.openai_gpt5_model
        )
        response = await httpx.AsyncClient(timeout=30.0).post(
            f"{self.config.openai_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": messages,
                "max_tokens": params.get("max_tokens", 1000),
                "temperature": params.get("temperature", 0.2),
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def check_model_health(self, model_id: str) -> dict[str, Any]:
        if model_id == "claude":
            healthy = bool(self.config.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", ""))
            return {"model": model_id, "healthy": healthy, "latency_ms": 0}
        if model_id in {"openai-gpt5", "openai-gpt45"}:
            healthy = bool(self.config.openai_api_key or os.getenv("OPENAI_API_KEY", ""))
            return {"model": model_id, "healthy": healthy, "latency_ms": 0}
        endpoint, _ = self._endpoint_and_key(ModelID(model_id))
        client = get_http_client(model_id)
        started = time.monotonic()
        try:
            response = await asyncio.wait_for(client.get(f"{endpoint}/health"), timeout=2.0)
            return {
                "model": model_id,
                "healthy": response.status_code == 200,
                "latency_ms": int((time.monotonic() - started) * 1000),
                "endpoint": endpoint,
            }
        except Exception as exc:
            return {"model": model_id, "healthy": False, "error": str(exc)[:100]}

    async def check_all_models_health(self) -> dict[str, Any]:
        model_names = ["phi3-mini", "mistral-7b", "llama3-8b", "codellama-13b", "claude", "openai-gpt5", "openai-gpt45"]
        results = await asyncio.gather(*[self.check_model_health(name) for name in model_names])
        health_map = {item["model"]: item for item in results}
        overall = "healthy" if health_map["phi3-mini"]["healthy"] else "critical"
        if overall == "healthy":
            gpu_up = any(health_map[name]["healthy"] for name in ("llama3-8b", "codellama-13b"))
            overall = "healthy" if gpu_up else "degraded"
        return {"overall": overall, "models": health_map}

    async def _dispatch_agent_tool(self, tool: str, params: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        nc = await self._get_nats()
        task_id = str(params.get("task_id") or f"{tool}-{uuid.uuid4().hex[:12]}")
        subject = spec["subject"]
        result_subject = f"{subject}.results"
        meta_decision = params.get("meta_decision")
        if isinstance(meta_decision, MetaDecisionEvent):
            meta_decision_payload = meta_decision.model_dump()
        elif isinstance(meta_decision, dict):
            meta_decision_payload = meta_decision
        else:
            meta_decision_payload = None
        payload = {
            **AgentTask(
                task_id=task_id,
                type=spec["task_type"],
                entity_id=params.get("entity_id"),
                entity_type=params.get("entity_type"),
                execution_mode=str(params.get("execution_mode", "prepare")),
                payload=params,
                correlation_id=str(params.get("correlation_id") or uuid.uuid4()),
                causation_id=str(params.get("causation_id") or task_id),
                retry_count=int(params.get("retry_count", 0)),
                idempotency_key=str(params.get("idempotency_key") or uuid.uuid4().hex),
            ).model_dump(),
            **params,
        }
        if meta_decision_payload is not None:
            payload["meta_decision"] = meta_decision_payload
        subscription = await nc.subscribe(result_subject)
        try:
            await nc.publish(subject, json.dumps(payload).encode())
            deadline = time.monotonic() + (self.config.agent_task_timeout_ms / 1000)
            while True:
                timeout = max(0.1, deadline - time.monotonic())
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for {tool} result on {result_subject}")
                msg = await subscription.next_msg(timeout=timeout)
                data = json.loads(msg.data.decode())
                if data.get("task_id") == task_id:
                    return data
        finally:
            await subscription.unsubscribe()

    async def _call_trust_engine_sot(self, params: dict[str, Any]) -> dict[str, Any]:
        headers = {}
        if self.config.internal_api_token:
            headers["x-cortex-internal-token"] = self.config.internal_api_token
        async with httpx.AsyncClient(
            base_url=self.config.trust_engine_url,
            timeout=10.0,
            headers=headers,
        ) as client:
            response = await client.post("/trust/sot/issue", json=params)
            response.raise_for_status()
            return response.json()

    async def _get_nats(self):
        global _nats_client
        if _nats_client is None or _nats_client.is_closed:
            import nats
            _nats_client = await nats.connect(self.config.nats_url)
        return _nats_client

    def _endpoint_and_key(self, model_id: ModelID) -> tuple[str, str]:
        env_endpoint, env_key = MODEL_ENV_MAP[model_id]
        fallback_endpoint = {
            ModelID.PHI3_MINI: self.config.phi3_endpoint,
            ModelID.MISTRAL_7B: self.config.mistral_endpoint,
            ModelID.LLAMA3_8B: self.config.llama3_endpoint,
            ModelID.CODELLAMA_13B: self.config.codellama_endpoint,
        }[model_id]
        fallback_key = {
            ModelID.PHI3_MINI: self.config.phi3_api_key,
            ModelID.MISTRAL_7B: self.config.mistral_api_key,
            ModelID.LLAMA3_8B: self.config.llama3_api_key,
            ModelID.CODELLAMA_13B: self.config.codellama_api_key,
        }[model_id]
        return os.getenv(env_endpoint, fallback_endpoint), os.getenv(env_key, fallback_key)
