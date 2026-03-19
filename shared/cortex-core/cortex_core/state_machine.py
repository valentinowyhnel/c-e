from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class IsolationState(str, Enum):
    FREE = "free"
    MONITORED = "monitored"
    SUSPECTED = "suspected"
    OBSERVATION = "observation"
    RESTRICTED = "restricted"
    QUARANTINED = "quarantined"
    IDENTITY_REVOKED = "identity_revoked"
    FORENSIC_PRESERVED = "forensic_preserved"
    ISOLATED = "isolated"
    RECOVERY_PENDING = "recovery_pending"
    RESTORED = "restored"
    FAILED = "failed"


ALLOWED_TRANSITIONS: dict[IsolationState, set[IsolationState]] = {
    IsolationState.FREE: {IsolationState.MONITORED, IsolationState.SUSPECTED},
    IsolationState.MONITORED: {IsolationState.FREE, IsolationState.SUSPECTED, IsolationState.OBSERVATION},
    IsolationState.SUSPECTED: {IsolationState.MONITORED, IsolationState.OBSERVATION, IsolationState.RESTRICTED},
    IsolationState.OBSERVATION: {IsolationState.MONITORED, IsolationState.RESTRICTED, IsolationState.QUARANTINED},
    IsolationState.RESTRICTED: {IsolationState.OBSERVATION, IsolationState.QUARANTINED},
    IsolationState.QUARANTINED: {IsolationState.FORENSIC_PRESERVED, IsolationState.RECOVERY_PENDING},
    IsolationState.FORENSIC_PRESERVED: {IsolationState.IDENTITY_REVOKED, IsolationState.ISOLATED},
    IsolationState.IDENTITY_REVOKED: {IsolationState.ISOLATED},
    IsolationState.ISOLATED: {IsolationState.RECOVERY_PENDING, IsolationState.FAILED},
    IsolationState.RECOVERY_PENDING: {IsolationState.RESTORED, IsolationState.FAILED},
    IsolationState.RESTORED: {IsolationState.FREE},
    IsolationState.FAILED: set(),
}


@dataclass(slots=True)
class StateTransitionRecord:
    from_state: IsolationState
    to_state: IsolationState
    reason: str
    timestamp: float = field(default_factory=time.time)


@dataclass(slots=True)
class TransitionResult:
    allowed: bool
    from_state: IsolationState
    to_state: IsolationState
    reason: str


def transition_isolation_state(current: IsolationState, new: IsolationState, reason: str) -> TransitionResult:
    if new in ALLOWED_TRANSITIONS.get(current, set()):
        return TransitionResult(True, current, new, reason)
    return TransitionResult(False, current, current, f"invalid_transition:{current.value}->{new.value}:{reason}")
