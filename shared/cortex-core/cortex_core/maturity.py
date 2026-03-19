from __future__ import annotations

from dataclasses import dataclass

from .contracts import CapabilityMaturity


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    name: str
    maturity: CapabilityMaturity
    notes: str


CAPABILITY_REGISTRY: dict[str, CapabilityDescriptor] = {
    "ad_read_validations": CapabilityDescriptor("ad_read_validations", CapabilityMaturity.PREPROD_READY, "LDAP/BloodHound reads and validations are implemented."),
    "ad_destructive_writes": CapabilityDescriptor("ad_destructive_writes", CapabilityMaturity.STUBBED, "Multiple AD write paths remain stubbed or partially verified."),
    "sot_issue": CapabilityDescriptor("sot_issue", CapabilityMaturity.PREPROD_READY, "SOT issuance path exists and is used by trust/sentinel."),
    "local_quarantine": CapabilityDescriptor("local_quarantine", CapabilityMaturity.BETA, "iptables-based local isolation exists but depends on host capabilities."),
    "irreversible_containment": CapabilityDescriptor("irreversible_containment", CapabilityMaturity.EXPERIMENTAL, "Irreversible containment must remain approval-gated."),
    "decision_committee": CapabilityDescriptor("decision_committee", CapabilityMaturity.BETA, "Committee workflow exists but depends on external models."),
    "model_governance_writes": CapabilityDescriptor("model_governance_writes", CapabilityMaturity.BETA, "Console writes require live Vault token integration."),
    "bloodhound_exposure_analysis": CapabilityDescriptor("bloodhound_exposure_analysis", CapabilityMaturity.PREPROD_READY, "Exposure and path analysis are wired through agent AD."),
}

PRODUCTION_CRITICAL_CAPABILITIES = {
    "ad_read_validations",
    "ad_destructive_writes",
    "sot_issue",
    "local_quarantine",
    "irreversible_containment",
    "decision_committee",
    "model_governance_writes",
    "bloodhound_exposure_analysis",
}


def production_maturity_blockers() -> list[str]:
    blockers: list[str] = []
    for name in sorted(PRODUCTION_CRITICAL_CAPABILITIES):
        capability = CAPABILITY_REGISTRY[name]
        if capability.maturity is not CapabilityMaturity.PRODUCTION_READY:
            blockers.append(f"{name}={capability.maturity.value}")
    return blockers
