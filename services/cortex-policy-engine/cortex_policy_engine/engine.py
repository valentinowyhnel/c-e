from __future__ import annotations

from pydantic import BaseModel, Field

from cortex_core.contracts import (  # noqa: E402
    ActionClass,
    ExecutionDecision,
    ExecutionGuardrails,
    RiskEnvelope,
)
from cortex_core.degraded import (  # noqa: E402
    block_irreversible_actions,
    external_llm_advisory_only,
    graph_degraded,
    maturity_allowed_in_environment,
    secret_rotation_allowed,
)
from cortex_core.maturity import CAPABILITY_REGISTRY  # noqa: E402


class PolicyDecision(BaseModel):
    decision: ExecutionDecision
    rationale: list[str] = Field(default_factory=list)
    approval_required: bool = False
    prepare_only: bool = False
    forensic_required: bool = False
    blocked_by: list[str] = Field(default_factory=list)


class PolicyEngine:
    def evaluate(
        self,
        envelope: RiskEnvelope,
        guardrails: ExecutionGuardrails,
        capability_name: str,
    ) -> PolicyDecision:
        rationale: list[str] = []
        blocked_by: list[str] = []
        capability = CAPABILITY_REGISTRY[capability_name]
        admin_compromise_score = float(envelope.derived_signals.get("admin_compromise_score", 0.0))
        insider_decay_score = float(envelope.derived_signals.get("insider_trust_decay", 0.0))

        if envelope.dry_run and envelope.action_class != ActionClass.READ_ONLY:
            rationale.append("Dry-run enforces prepare-only path.")
            if not maturity_allowed_in_environment(capability.maturity, envelope.environment):
                rationale.append("Capability maturity too low for execution, but dry-run remains allowed.")
            return PolicyDecision(
                decision=ExecutionDecision.PREPARE_ONLY,
                rationale=rationale,
                prepare_only=True,
                forensic_required=guardrails.forensic_required,
            )

        if not maturity_allowed_in_environment(capability.maturity, envelope.environment):
            blocked_by.append(f"maturity:{capability.maturity.value}")
            return PolicyDecision(
                decision=ExecutionDecision.DENIED,
                rationale=["Capability maturity too low for environment."],
                blocked_by=blocked_by,
            )

        if envelope.action_class == ActionClass.IRREVERSIBLE and block_irreversible_actions(envelope.dependencies):
            blocked_by.append("critical_degraded_mode")
            return PolicyDecision(
                decision=ExecutionDecision.BLOCKED_DUE_TO_DEGRADED_MODE,
                rationale=["Critical dependency unavailable. Irreversible action blocked."],
                blocked_by=blocked_by,
                forensic_required=guardrails.forensic_required,
            )

        if "admin:write" not in envelope.scopes and envelope.action_class in {
            ActionClass.EXECUTE_WITH_APPROVAL,
            ActionClass.IRREVERSIBLE,
        }:
            blocked_by.append("missing_scope:admin:write")
            return PolicyDecision(
                decision=ExecutionDecision.DENIED,
                rationale=["Caller lacks admin:write scope."],
                blocked_by=blocked_by,
            )

        if admin_compromise_score >= 85.0 and envelope.action_class in {
            ActionClass.EXECUTE_WITH_APPROVAL,
            ActionClass.IRREVERSIBLE,
        }:
            return PolicyDecision(
                decision=ExecutionDecision.APPROVAL_REQUIRED,
                rationale=[
                    "Admin compromise suspicion exceeds escalation threshold.",
                    "Step-up approval required before critical admin execution.",
                ],
                approval_required=True,
                forensic_required=True,
                blocked_by=["admin_compromise_suspected"],
            )

        if insider_decay_score >= 65.0 and envelope.criticality in {"high", "critical"}:
            return PolicyDecision(
                decision=ExecutionDecision.APPROVAL_REQUIRED,
                rationale=[
                    "Insider trust decay exceeds threshold for sensitive asset access.",
                    "Human approval required while trust recovers or is disproved.",
                ],
                approval_required=True,
                forensic_required=guardrails.forensic_required,
                blocked_by=["insider_trust_decay"],
            )

        if envelope.action == "execute_secret_rotation" and not secret_rotation_allowed(envelope.dependencies):
            return PolicyDecision(
                decision=ExecutionDecision.BLOCKED_DUE_TO_DEGRADED_MODE,
                rationale=["Vault unavailable. Secret rotation denied."],
                blocked_by=["vault_unavailable"],
            )

        if envelope.action in {"execute_quarantine", "execute_irreversible_containment"} and envelope.blast_radius > 25:
            rationale.append("Blast radius exceeds autonomous threshold.")
            return PolicyDecision(
                decision=ExecutionDecision.APPROVAL_REQUIRED,
                rationale=rationale,
                approval_required=True,
                forensic_required=guardrails.forensic_required,
            )

        if envelope.strong_signal_count < guardrails.min_sources and envelope.action_class == ActionClass.IRREVERSIBLE:
            blocked_by.append("insufficient_independent_sources")
            return PolicyDecision(
                decision=ExecutionDecision.PREPARE_ONLY,
                rationale=["Insufficient independent signals for irreversible action."],
                prepare_only=True,
                blocked_by=blocked_by,
                forensic_required=True,
            )

        if envelope.trust_score < guardrails.min_trust_score:
            rationale.append("Trust score below guardrail threshold.")

        if envelope.crown_jewels_exposed or envelope.criticality in {"high", "critical"}:
            rationale.append("Crown jewel or business critical asset involved.")
            if envelope.action_class in {ActionClass.EXECUTE_WITH_APPROVAL, ActionClass.IRREVERSIBLE}:
                return PolicyDecision(
                    decision=ExecutionDecision.APPROVAL_REQUIRED,
                    rationale=rationale,
                    approval_required=True,
                    forensic_required=guardrails.forensic_required,
                )

        if graph_degraded(envelope.dependencies) and envelope.action in {
            "prepare_quarantine",
            "execute_quarantine",
            "execute_irreversible_containment",
        }:
            rationale.append("Graph degraded; blast radius is partial.")
            return PolicyDecision(
                decision=ExecutionDecision.PREPARE_ONLY,
                rationale=rationale,
                prepare_only=True,
                forensic_required=guardrails.forensic_required,
            )

        if external_llm_advisory_only(envelope.dependencies):
            rationale.append("External LLM unavailable; advisory enrichment disabled.")

        if guardrails.approval_required or envelope.action_class == ActionClass.EXECUTE_WITH_APPROVAL:
            return PolicyDecision(
                decision=ExecutionDecision.APPROVAL_REQUIRED,
                rationale=rationale or ["Action class requires approval."],
                approval_required=True,
                forensic_required=guardrails.forensic_required,
            )

        if envelope.action_class == ActionClass.PREPARE_ONLY:
            return PolicyDecision(
                decision=ExecutionDecision.PREPARE_ONLY,
                rationale=rationale or ["Action exposed only as prepare step."],
                prepare_only=True,
                forensic_required=guardrails.forensic_required,
            )

        return PolicyDecision(
            decision=ExecutionDecision.ALLOWED,
            rationale=rationale or ["Policy evaluation passed."],
            forensic_required=guardrails.forensic_required,
        )
