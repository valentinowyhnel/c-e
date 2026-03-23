from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .config import MCPServerConfig
from .executor import MCPExecutor
from .filters import InputFilter, OutputFilter
from .modes.batch import BatchProcessor, BatchRequest
from .modes.dryrun import DryRunEngine
from .modes.multiturn import ContextWindowManager, ConversationContext, Turn
from .plugins.pipeline import MetricsRegistry, PipelineContext, PluginPipeline
from .plugins.registry import ENABLED_PLUGINS
from .router import ModelID, RouterConfig, SmartModelRouter

from cortex_core.contracts import (  # noqa: E402
    ActionClass,
    CapabilityMaturity,
    DependencyHealthSnapshot,
    DependencyState,
    ExecutionGuardrails,
    RiskEnvelope,
)
from cortex_core.meta_decision import DeepAnalysisRequest, MetaDecisionEvent  # noqa: E402
from cortex_policy_engine.engine import PolicyEngine  # noqa: E402


class ToolCallRequest(BaseModel):
    tool: str
    params: dict[str, object] = Field(default_factory=dict)
    agent_id: str
    agent_scopes: list[str] = Field(default_factory=list)
    meta_decision: MetaDecisionEvent | None = None


class DeepAnalysisRelayRequest(BaseModel):
    requests: list[DeepAnalysisRequest] = Field(default_factory=list)
    context: dict[str, object] = Field(default_factory=dict)
    agent_id: str = "meta_decision_agent"
    agent_scopes: list[str] = Field(default_factory=lambda: ["read:graph"])


class CompleteRequest(BaseModel):
    task: str
    input: str = ""
    params: dict[str, object] = Field(default_factory=dict)
    session_id: str | None = None
    dry_run: bool = False
    batch: dict[str, object] | None = None
    expected_format: str = "text"
    strip_markdown: bool = False
    system_prompt: str = ""
    tool: str | None = None
    tool_params: dict[str, object] = Field(default_factory=dict)


class SentinelClient:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._fallback = LocalSentinelClient()

    async def check_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        params: dict[str, object],
        agent_scopes: list[str],
    ) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=self.config.sentinel_timeout_ms / 1000) as client:
                response = await client.post(
                    f"{self.config.sentinel_url}/v1/check-tool-call",
                    json={
                        "agent_id": agent_id,
                        "tool_name": tool_name,
                        "params": params,
                        "agent_scopes": agent_scopes,
                    },
                )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return await self._fallback.check_tool_call(agent_id, tool_name, params, agent_scopes)


class LocalSentinelClient:
    ADMIN_WRITE_TOOLS = {
        "delete_user",
        "disable_mfa",
        "ad_restore_deleted",
        "create_service_account",
        "reset_password",
        "disable_account",
        "move_to_ou",
        "add_to_group",
        "remove_from_group",
    }

    async def check_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        params: dict[str, object],
        agent_scopes: list[str],
    ) -> dict[str, object]:
        blocked = tool_name in self.ADMIN_WRITE_TOOLS and "admin:write" not in agent_scopes
        return {
            "allowed": not blocked,
            "reason": "missing admin:write scope" if blocked else "allowed",
            "agent_id": agent_id,
            "tool_name": tool_name,
        }


class AppState:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.router = SmartModelRouter(
            RouterConfig(),
            phi3_endpoint=config.phi3_endpoint,
            phi3_api_key=config.phi3_api_key,
        )
        self.input_filter = InputFilter(
            max_input_size=config.max_input_size,
            strict=config.prompt_injection_strict,
            redact_pii=config.pii_redaction_enabled,
        )
        self.output_filter = OutputFilter(config.max_output_size)
        self.executor = MCPExecutor(config)
        self.sentinel: SentinelClient | LocalSentinelClient = SentinelClient(config)
        self.dry_run = DryRunEngine()
        self.contexts = ContextWindowManager(config.session_ttl_seconds)
        self.batch = BatchProcessor(self.executor, self.sentinel)
        self.metrics = MetricsRegistry()
        self.pipeline = PluginPipeline(self.metrics)
        self.policy = PolicyEngine()


def _forced_model_decision(decision, forced_model: str | None):
    if not forced_model:
        return decision
    try:
        model = ModelID(forced_model)
    except Exception:
        return decision
    hardware = "cpu_local"
    if model in {ModelID.LLAMA3_8B, ModelID.CODELLAMA_13B}:
        hardware = "gpu_cloud"
    elif model in {ModelID.CLAUDE, ModelID.OPENAI_GPT5, ModelID.OPENAI_GPT45}:
        hardware = "api"
    decision.primary_model = model
    decision.fallback_model = ModelID.CLAUDE if model != ModelID.CLAUDE else ModelID.OPENAI_GPT5
    decision.hardware = hardware
    decision.reason = f"{decision.reason},forced_model={model.value}"
    decision.routing_source = "forced_model"
    return decision


def _force_model_allowed(app_state: AppState, forced_model: str | None, task: str, params: dict[str, object]) -> bool:
    if not forced_model:
        return True
    envelope = RiskEnvelope(
        entity_id=str(params.get("entity_id", "request")),
        entity_type=str(params.get("entity_type", "request")),
        action=f"force_model:{forced_model}",
        action_class=ActionClass.ADVISORY,
        trust_score=float(params.get("trust_score", 50.0)),
        threat_level=int(params.get("risk_level", 1)),
        scopes=list(params.get("scopes", ["read:graph"])),
        environment=str(params.get("environment", "preprod")),
        maturity=CapabilityMaturity.BETA,
        dependencies=DependencyHealthSnapshot(external_llm=DependencyState.HEALTHY),
    )
    decision = app_state.policy.evaluate(
        envelope,
        ExecutionGuardrails(action_class=ActionClass.ADVISORY),
        "decision_committee",
    )
    return decision.decision != "denied"


def create_app(config: MCPServerConfig | None = None) -> FastAPI:
    cfg = config or MCPServerConfig.load()
    state = AppState(cfg)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(
        title="Cortex MCP Server v2",
        version="2.0.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.cortex = state
    app.state.plugins = ENABLED_PLUGINS

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "cortex-mcp-server",
            "version": "2.0.0",
            "plugins": [plugin.name for plugin in ENABLED_PLUGINS if plugin.enabled],
        }

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", response_model=None)
    async def readyz():
        if not app.state.cortex.config.enforce_model_health:
            return {"status": "ready", "cpu_models": "check_disabled"}
        health = await app.state.cortex.executor.check_model_health("phi3-mini")
        if health["healthy"]:
            return {"status": "ready", "cpu_models": "available"}
        return Response(status_code=503)

    @app.get("/metrics")
    async def metrics() -> Response:
        body = app.state.cortex.pipeline.metrics.render()
        return Response(content=body, media_type="text/plain; version=0.0.4")

    @app.post("/mcp/debug/route")
    async def debug_route(req: CompleteRequest, request: Request) -> dict[str, object]:
        scopes = [scope for scope in request.headers.get("x-cortex-scopes", "").split(",") if scope]
        if "admin:write" not in scopes and "read:debug" not in scopes:
            raise HTTPException(status_code=403, detail={"error": "debug route requires read:debug or admin:write"})
        decision = await app.state.cortex.router.route(req.task or (req.tool or "complete"), req.model_dump())
        return {
            "task_type": decision.task_type.value,
            "model_id": decision.primary_model.value,
            "fallback_model": decision.fallback_model.value,
            "hardware": decision.hardware,
            "reason": decision.reason,
            "routing_source": decision.routing_source,
        }

    @app.post("/mcp/tools/call")
    async def call_tool(req: ToolCallRequest) -> dict[str, object]:
        correlation_id = str(uuid.uuid4())
        verdict = await app.state.cortex.sentinel.check_tool_call(
            agent_id=req.agent_id,
            tool_name=req.tool,
            params=req.params,
            agent_scopes=req.agent_scopes,
        )
        if not verdict["allowed"]:
            raise HTTPException(status_code=403, detail=verdict["reason"])
        safe_params = {**req.params, "scopes": req.agent_scopes, "correlation_id": correlation_id}
        if req.meta_decision is not None:
            safe_params["meta_decision"] = req.meta_decision.model_dump()
        result = await app.state.cortex.executor.execute_tool(req.tool, safe_params, req.agent_id)
        return {"correlation_id": correlation_id, "result": result, "sentinel": verdict}

    @app.post("/mcp/meta-decision/deep-analysis")
    async def relay_deep_analysis(req: DeepAnalysisRelayRequest) -> dict[str, object]:
        results = []
        for item in req.requests:
            params = {
                **req.context,
                "event_id": item.event_id,
                "entity_id": item.entity_id,
                "entity_type": str(req.context.get("entity_type", "unknown")),
                "deep_analysis_request": item.model_dump(),
                "execution_mode": "prepare",
            }
            result = await app.state.cortex.executor.execute_tool(
                "decision_explain_human",
                {**params, "scopes": req.agent_scopes},
                req.agent_id,
            )
            results.append({"request": item.model_dump(), "result": result})
        return {"accepted": True, "results": results}

    @app.post("/mcp/complete")
    async def complete(req: CompleteRequest, request: Request) -> dict[str, object]:
        body = req.model_dump()
        correlation_id = request.headers.get("x-cortex-correlation-id", str(uuid.uuid4()))
        agent_id = request.headers.get("x-cortex-user-id", "unknown")
        scopes = [scope for scope in request.headers.get("x-cortex-scopes", "").split(",") if scope]

        input_data = req.input
        filter_result = app.state.cortex.input_filter.filter(input_data, context=body)
        if filter_result.blocked:
            raise HTTPException(status_code=400, detail={"error": filter_result.reason})
        if filter_result.modified:
            input_data = str(filter_result.cleaned)

        if req.batch:
            batch_req = BatchRequest(
                batch_id=str(req.batch.get("batch_id", uuid.uuid4())),
                requests=list(req.batch.get("requests", [])),  # type: ignore[arg-type]
                parallel=int(req.batch.get("parallel", 4)),
                timeout_ms=int(req.batch.get("timeout_ms", 30_000)),
            )
            result = await app.state.cortex.batch.process(batch_req, agent_id, scopes)
            return {
                "batch_id": result.batch_id,
                "results": result.results,
                "failed": result.failed,
                "duration_ms": result.duration_ms,
            }

        task = req.task or (req.tool or "complete")
        ctx_pipeline = PipelineContext(
            request_id=correlation_id,
            agent_id=agent_id,
            task=task,
            input_data=input_data,
            params=body,
            session_id=req.session_id,
            dry_run=req.dry_run,
        )
        ctx_pipeline = await app.state.cortex.pipeline.before_route(ctx_pipeline)
        decision = await app.state.cortex.router.route(task, body)
        forced_model = str(req.params.get("force_model", "")) or None
        if forced_model and not _force_model_allowed(app.state.cortex, forced_model, task, {**req.params, "scopes": scopes}):
            raise HTTPException(status_code=403, detail={"error": "force_model denied by policy"})
        decision = _forced_model_decision(decision, forced_model)
        ctx_pipeline.task_type = decision.task_type.value
        ctx_pipeline.model_id = decision.primary_model.value
        ctx_pipeline.hardware = decision.hardware
        ctx_pipeline = await app.state.cortex.pipeline.after_route(ctx_pipeline)

        messages: list[dict[str, str]] = []
        session_id = req.session_id
        ctx_mgr = app.state.cortex.contexts
        ctx: ConversationContext | None = None
        if session_id:
            ctx = await ctx_mgr.load_context(session_id)
            if ctx is None:
                ctx = ConversationContext(
                    session_id=session_id,
                    agent_id=agent_id,
                    created_at=time.time(),
                    last_active=time.time(),
                )
            messages = ctx_mgr.build_messages(
                ctx,
                input_data,
                decision.primary_model,
                system_prompt=req.system_prompt,
            )
        else:
            if req.system_prompt:
                messages.append({"role": "system", "content": req.system_prompt})
            messages.append({"role": "user", "content": input_data})

        if req.dry_run and req.tool:
            dry_result = await app.state.cortex.dry_run.simulate(
                tool=req.tool,
                params=req.tool_params,
                agent_id=agent_id,
            )
            return {"dry_run_result": asdict(dry_result), "model_used": "dry_run_engine"}

        result = await app.state.cortex.executor.execute_with_fallback(
            decision=decision,
            messages=messages,
            generation_params={
                "max_tokens": int(req.params.get("max_tokens", 1000)),
                "temperature": float(req.params.get("temperature", 0.3)),
                "expected_format": str(req.params.get("expected_format", req.expected_format)),
            },
            agent_id=agent_id,
            audit=None,
        )

        out_filter = app.state.cortex.output_filter.filter(
            str(result["content"]),
            expected_format=str(req.params.get("expected_format", req.expected_format)),
            strip_markdown=bool(req.params.get("strip_markdown", req.strip_markdown)),
        )
        if out_filter.blocked:
            raise HTTPException(status_code=500, detail={"error": out_filter.reason})

        final_output = out_filter.cleaned if out_filter.modified else result["content"]
        ctx_pipeline.output = str(final_output)
        ctx_pipeline.model_used = str(result["model_used"])
        ctx_pipeline.was_fallback = bool(result.get("was_fallback", False))
        await app.state.cortex.pipeline.after_execute(ctx_pipeline)

        if session_id and ctx is not None:
            ctx.turns.append(
                Turn(
                    role="user",
                    content=input_data,
                    timestamp=time.time(),
                    model_id=decision.primary_model.value,
                    tokens=max(1, len(input_data) // 4),
                )
            )
            ctx.turns.append(
                Turn(
                    role="assistant",
                    content=str(final_output),
                    timestamp=time.time(),
                    model_id=str(result["model_used"]),
                    tokens=max(1, len(str(final_output)) // 4),
                )
            )
            await ctx_mgr.save_context(ctx)

        return {
            "correlation_id": correlation_id,
            "output": final_output,
            "model_used": result["model_used"],
            "was_fallback": result.get("was_fallback", False),
            "task_type": decision.task_type.value,
            "hardware": decision.hardware,
            "session_id": session_id,
            "routing_source": decision.routing_source,
        }

    return app


app = create_app()
