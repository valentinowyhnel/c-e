from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Plugin:
    name: str
    version: str
    hooks: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 50
    description: str = ""


ENABLED_PLUGINS = [
    Plugin(
        name="observability",
        version="1.0.0",
        priority=10,
        description="Tracks latency and routing metadata",
        hooks={"post_route": "record_routing_decision", "post_execute": "record_execution_metrics"},
    ),
    Plugin(
        name="retry",
        version="1.0.0",
        priority=30,
        description="Placeholder retry and backoff hook set",
        hooks={"on_error": "maybe_retry", "on_timeout": "maybe_retry_with_fallback"},
    ),
    Plugin(
        name="tenant_isolation",
        version="1.0.0",
        priority=5,
        description="Separates multi-turn sessions by tenant",
        hooks={"post_auth": "inject_tenant_context", "post_output": "strip_cross_tenant_data"},
    ),
]
