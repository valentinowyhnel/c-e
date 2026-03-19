from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DRY_RUN_SUPPORTED_TOOLS = {
    "revoke_user_sessions",
    "isolate_account",
    "deploy_policy",
    "bulk_update_groups",
    "delete_user",
    "modify_ad_group",
    "rotate_credentials",
    "change_trust_score",
    "apply_network_policy",
    "add_to_group",
    "remove_from_group",
    "create_service_account",
    "restore_deleted",
    "move_to_ou",
    "disable_account",
    "reset_password",
    "ad_restore_deleted",
}

DRY_RUN_REQUIRED_TOOLS = {
    "revoke_user_sessions",
    "isolate_account",
    "deploy_policy",
    "delete_user",
    "bulk_update_groups",
    "create_service_account",
    "restore_deleted",
    "ad_restore_deleted",
}


@dataclass(slots=True)
class DryRunResult:
    tool: str
    params: dict[str, Any]
    would_succeed: bool
    simulated_output: Any
    side_effects: list[str]
    entities_affected: list[str]
    risk_assessment: dict[str, Any]
    warnings: list[str]
    blocking_issues: list[str]


class DryRunEngine:
    async def simulate(self, tool: str, params: dict[str, Any], agent_id: str) -> DryRunResult:
        if tool not in DRY_RUN_SUPPORTED_TOOLS:
            return DryRunResult(
                tool=tool,
                params=params,
                would_succeed=False,
                simulated_output=None,
                side_effects=[],
                entities_affected=[],
                risk_assessment={},
                warnings=[],
                blocking_issues=[f"tool '{tool}' does not support dry-run"],
            )

        target = str(params.get("user_id") or params.get("entity_id") or params.get("policy_id") or "unknown")
        return DryRunResult(
            tool=tool,
            params=params,
            would_succeed=True,
            simulated_output={"tool": tool, "status": "simulated", "agent_id": agent_id},
            side_effects=[f"{tool} would affect target {target}", "Audit events would be emitted"],
            entities_affected=[target] if target != "unknown" else [],
            risk_assessment={"risk_level": 4 if tool in DRY_RUN_REQUIRED_TOOLS else 2},
            warnings=["dry-run required before execution"] if tool in DRY_RUN_REQUIRED_TOOLS else [],
            blocking_issues=[],
        )
