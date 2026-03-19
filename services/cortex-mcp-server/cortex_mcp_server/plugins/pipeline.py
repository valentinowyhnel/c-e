from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PipelineContext:
    request_id: str
    agent_id: str
    task: str
    input_data: str
    params: dict[str, Any]
    session_id: str | None
    task_type: str = ""
    model_id: str = ""
    hardware: str = ""
    output: str = ""
    model_used: str = ""
    was_fallback: bool = False
    cache_hit: bool = False
    dry_run: bool = False
    blocked: bool = False
    block_reason: str = ""
    start_time: float = field(default_factory=time.monotonic)
    routing_time_ms: int = 0
    exec_time_ms: int = 0

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.start_time) * 1000)


class MetricsRegistry:
    def __init__(self) -> None:
        self.calls_total: dict[tuple[str, str, str], int] = {}
        self.fallbacks_total: dict[tuple[str, str], int] = {}
        self.cache_hits_total: dict[str, int] = {}
        self.latency_samples: dict[tuple[str, str], list[float]] = {}

    def inc_call(self, model: str, task_type: str, outcome: str) -> None:
        key = (model, task_type, outcome)
        self.calls_total[key] = self.calls_total.get(key, 0) + 1

    def inc_fallback(self, from_model: str, to_model: str) -> None:
        key = (from_model, to_model)
        self.fallbacks_total[key] = self.fallbacks_total.get(key, 0) + 1

    def inc_cache_hit(self, task_type: str) -> None:
        self.cache_hits_total[task_type] = self.cache_hits_total.get(task_type, 0) + 1

    def observe_latency(self, model: str, task_type: str, seconds: float) -> None:
        key = (model, task_type)
        self.latency_samples.setdefault(key, []).append(seconds)

    def render(self) -> str:
        lines = [
            "# HELP cortex_mcp_server_up Cortex MCP server availability",
            "# TYPE cortex_mcp_server_up gauge",
            "cortex_mcp_server_up 1",
            "# HELP cortex_mcp_calls_total Total MCP calls",
            "# TYPE cortex_mcp_calls_total counter",
        ]
        for (model, task_type, outcome), value in sorted(self.calls_total.items()):
            lines.append(
                f'cortex_mcp_calls_total{{model="{model}",task_type="{task_type}",outcome="{outcome}"}} {value}'
            )
        lines.extend(
            [
                "# HELP cortex_mcp_fallbacks_total Model fallbacks triggered",
                "# TYPE cortex_mcp_fallbacks_total counter",
            ]
        )
        for (from_model, to_model), value in sorted(self.fallbacks_total.items()):
            lines.append(
                f'cortex_mcp_fallbacks_total{{from_model="{from_model}",to_model="{to_model}"}} {value}'
            )
        lines.extend(
            [
                "# HELP cortex_mcp_cache_hits_total Semantic cache hits",
                "# TYPE cortex_mcp_cache_hits_total counter",
            ]
        )
        for task_type, value in sorted(self.cache_hits_total.items()):
            lines.append(f'cortex_mcp_cache_hits_total{{task_type="{task_type}"}} {value}')
        lines.extend(
            [
                "# HELP cortex_mcp_call_duration_seconds MCP call duration",
                "# TYPE cortex_mcp_call_duration_seconds summary",
            ]
        )
        for (model, task_type), samples in sorted(self.latency_samples.items()):
            if not samples:
                continue
            count = len(samples)
            total = sum(samples)
            lines.append(
                f'cortex_mcp_call_duration_seconds_count{{model="{model}",task_type="{task_type}"}} {count}'
            )
            lines.append(
                f'cortex_mcp_call_duration_seconds_sum{{model="{model}",task_type="{task_type}"}} {total}'
            )
        lines.append("")
        return "\n".join(lines)


class PluginPipeline:
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics

    async def before_route(self, ctx: PipelineContext) -> PipelineContext:
        return ctx

    async def after_route(self, ctx: PipelineContext) -> PipelineContext:
        return ctx

    async def after_execute(self, ctx: PipelineContext) -> PipelineContext:
        outcome = "cache_hit" if ctx.cache_hit else ("fallback" if ctx.was_fallback else "success")
        model = ctx.model_used or ctx.model_id or "unknown"
        task_type = ctx.task_type or "unknown"
        self.metrics.inc_call(model, task_type, outcome)
        self.metrics.observe_latency(model, task_type, ctx.elapsed_ms() / 1000)
        if ctx.was_fallback and ctx.model_id and ctx.model_used:
            self.metrics.inc_fallback(ctx.model_id, ctx.model_used)
        return ctx
