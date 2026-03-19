from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import sys
from pathlib import Path

from .client import MCPClient

ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_core.contracts import CapabilityMaturity, ExecutionMode  # noqa: E402


@dataclass
class AgentResult:
    task_id: str
    agent_id: str
    success: bool
    output: dict[str, Any]
    reasoning: str
    actions_taken: list[dict[str, Any]]
    requires_approval: bool
    approval_payload: dict[str, Any] | None
    duration_ms: int
    tokens_used: int
    model_used: str = ""
    execution_mode: str = ExecutionMode.EXECUTE.value
    capability_maturity: str = CapabilityMaturity.BETA.value


class CortexBaseAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.mcp = MCPClient(agent_id=agent_id)
