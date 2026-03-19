from __future__ import annotations

from .contracts import CapabilityMaturity, DependencyHealthSnapshot, DependencyState


def block_irreversible_actions(snapshot: DependencyHealthSnapshot) -> bool:
    if snapshot.approval == DependencyState.UNAVAILABLE:
        return True
    if snapshot.nats == DependencyState.UNAVAILABLE:
        return True
    if snapshot.sentinel == DependencyState.UNAVAILABLE:
        return True
    return False


def secret_rotation_allowed(snapshot: DependencyHealthSnapshot) -> bool:
    return snapshot.vault == DependencyState.HEALTHY


def graph_degraded(snapshot: DependencyHealthSnapshot) -> bool:
    return any(state != DependencyState.HEALTHY for state in (snapshot.neo4j, snapshot.bloodhound))


def external_llm_advisory_only(snapshot: DependencyHealthSnapshot) -> bool:
    return snapshot.external_llm != DependencyState.HEALTHY


def maturity_allowed_in_environment(maturity: CapabilityMaturity, environment: str) -> bool:
    if environment == "prod":
        return maturity in {CapabilityMaturity.PRODUCTION_READY}
    if environment == "preprod":
        return maturity in {CapabilityMaturity.PRODUCTION_READY, CapabilityMaturity.PREPROD_READY, CapabilityMaturity.BETA}
    return maturity != CapabilityMaturity.STUBBED
