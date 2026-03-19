from __future__ import annotations

import asyncio
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
import structlog

from .collectors.psutil_col import CollectedEvent, SentinelCollector

try:
    import cortex_core  # noqa: F401
except ImportError:
    candidate = Path(__file__).resolve()
    for parent in candidate.parents:
        root = parent / "shared" / "cortex-core"
        if root.exists():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            break

from cortex_core.contracts import (  # noqa: E402
    ActionClass,
    DependencyHealthSnapshot,
    DependencyState,
    ExecutionGuardrails,
    RiskEnvelope,
    SOTRecord,
)
from cortex_core.degraded import block_irreversible_actions  # noqa: E402
from cortex_core.state_machine import (  # noqa: E402
    IsolationState,
    transition_isolation_state,
)

log = structlog.get_logger()

APOPTOSIS_THRESHOLD = 20.0
CRITICAL_THRESHOLD = 40.0
OBSERVATION_THRESHOLD = 55.0
HEALTHY_THRESHOLD = 80.0
DECAY_SPEED = 1.0
RECOVERY_SPEED = 0.25
SOT_TTL_SECONDS = 1800
HARD_STOP_SIGNALS = {
    "confirmed_credential_dump",
    "Security Tool Killed",
    "Credential Dump Attempt",
    "confirmed_ransomware_behavior",
    "workload_identity_key_compromise",
}
DETECTOR_CONFIDENCE = {
    "falco_rule": 0.88,
    "auditd_exec": 0.85,
    "auditd_connect": 0.80,
    "psutil_process": 0.70,
}
CONTEXT_MULTIPLIERS = {
    "crown_jewel_access": 2.0,
    "identity_store": 2.0,
    "payment_data": 1.8,
    "admin_scope": 1.5,
    "production_env": 1.3,
    "normal_resource": 1.0,
}


@dataclass
class EntityState:
    entity_id: str
    entity_type: str
    current_score: float = 85.0
    baseline_score: float = 85.0
    isolation_state: IsolationState = IsolationState.FREE
    entity_group: str = "default"
    is_protected: bool = False
    active_sot_id: str | None = None

    def transition_to(self, new: IsolationState) -> bool:
        result = transition_isolation_state(self.isolation_state, new, "sentinel_transition")
        if result.allowed:
            self.isolation_state = new
        return result.allowed


def freshness_factor(age_seconds: float, ttl: int) -> float:
    if age_seconds >= ttl:
        return 0.0
    return max(0.1, 1.0 - (age_seconds / ttl))


def _recommend_action(score: float, state: EntityState) -> str:
    if state.is_protected:
        return "alert_human_only"
    if score < APOPTOSIS_THRESHOLD:
        return "prepare_irreversible_containment"
    if score < CRITICAL_THRESHOLD:
        return "prepare_quarantine"
    if score < OBSERVATION_THRESHOLD:
        return "issue_sot"
    if score < 70.0:
        return "restrict"
    if score < HEALTHY_THRESHOLD:
        return "monitor"
    return "none"


def compute_score(state: EntityState, events: list[CollectedEvent], context: str = "normal_resource") -> tuple[float, str, bool, str | None]:
    ctx_mult = CONTEXT_MULTIPLIERS.get(context, 1.0)
    delta = 0.0
    hard_stop = False
    hard_stop_sig: str | None = None
    for ev in events:
        if ev.event_type in HARD_STOP_SIGNALS or ev.metadata.get("hard_stop"):
            hard_stop = True
            hard_stop_sig = ev.event_type
            break
        age = time.time() - ev.timestamp
        fresh = freshness_factor(age, ttl=300)
        src_conf = DETECTOR_CONFIDENCE.get(ev.source, ev.confidence)
        impact = ev.severity * min(ev.confidence, src_conf) * fresh * ctx_mult
        if ev.severity > 0.5:
            delta -= impact * DECAY_SPEED
        else:
            delta += impact * RECOVERY_SPEED
    if hard_stop:
        return 0.0, "immediate_quarantine", True, hard_stop_sig
    new_score = state.current_score + delta
    if delta > 0 and new_score > state.baseline_score:
        overshoot = new_score - state.baseline_score
        new_score = state.baseline_score + overshoot * 0.2
    new_score = max(0.0, min(100.0, new_score))
    return round(new_score, 2), _recommend_action(new_score, state), False, None


def update_baseline(state: EntityState, window_days: int = 7) -> float:
    alpha = 2 / (window_days + 1)
    return round(alpha * state.current_score + (1 - alpha) * state.baseline_score, 2)


def check_multi_source(events: list[CollectedEvent], min_sources: int = 2) -> bool:
    return len({ev.source for ev in events if ev.severity > 0.6}) >= min_sources


class CortexSentinelEngine:
    POLL_INTERVAL = 3.0

    def __init__(self, entity_id: str, entity_type: str, nats_client: Any, trust_engine_url: str = "http://cortex-trust-engine:8080"):
        self.state = EntityState(entity_id=entity_id, entity_type=entity_type)
        self.nats = nats_client
        self.collector = SentinelCollector(entity_id)
        self._http = httpx.AsyncClient(base_url=trust_engine_url, timeout=5.0)
        self._running = False
        self._dependency_snapshot = DependencyHealthSnapshot(
            nats=DependencyState.HEALTHY,
            sentinel=DependencyState.HEALTHY,
            approval=DependencyState.HEALTHY,
        )

    async def _publish(self, subject: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode()
        try:
            await self.nats.jetstream().publish(subject, encoded)
            return
        except Exception as exc:
            log.warning("sentinel.publish.jetstream_failed", subject=subject, error=str(exc)[:200])
        await self.nats.publish(subject, encoded)

    async def run(self) -> None:
        self._running = True
        asyncio.create_task(self._watchdog_loop())
        while self._running:
            try:
                await self._cycle()
            except Exception as exc:
                log.error("sentinel.cycle.error", error=str(exc)[:200])
            await asyncio.sleep(self.POLL_INTERVAL)

    async def _cycle(self) -> None:
        events = self.collector.collect()
        if not events:
            return
        if self.state.isolation_state == IsolationState.FREE:
            self.state.transition_to(IsolationState.MONITORED)
        for ev in events:
            await self._publish(
                "cortex.obs.stream",
                {
                    "entity_id": self.state.entity_id,
                    "event_type": ev.event_type,
                    "source": ev.source,
                    "severity": ev.severity,
                    "confidence": ev.confidence,
                    "command": ev.command,
                    "timestamp": ev.timestamp,
                },
            )
        new_score, action, hard_stop, hs_sig = compute_score(self.state, events, context=self._detect_context())
        old_score = self.state.current_score
        self.state.current_score = new_score
        self.state.baseline_score = update_baseline(self.state)
        await self._publish(
            "cortex.trust.updates",
            {
                "entity_id": self.state.entity_id,
                "entity_type": self.state.entity_type,
                "score_before": old_score,
                "score_after": new_score,
                "action": action,
                "hard_stop": hard_stop,
                "hs_signal": hs_sig,
                "timestamp": time.time(),
                "evidences": [
                    {
                        "signal_type": ev.event_type,
                        "source": ev.source,
                        "severity": ev.severity,
                        "confidence": ev.confidence,
                        "ttl_seconds": 300,
                    }
                    for ev in events
                ],
            },
        )
        await self._act(action, events, hard_stop, hs_sig)

    async def _act(self, action: str, events: list[CollectedEvent], hard_stop: bool, hs_sig: str | None) -> None:
        if action in {"none", "monitor"}:
            return
        if action == "restrict":
            self.state.transition_to(IsolationState.RESTRICTED)
            await self._publish(
                "cortex.security.events",
                {
                    "event_type": "local_restriction_applied",
                    "entity_id": self.state.entity_id,
                    "timestamp": time.time(),
                },
            )
            return
        if action == "issue_sot":
            if self.state.active_sot_id:
                return
            sot = SOTRecord(
                entity_id=self.state.entity_id,
                entity_type=self.state.entity_type,
                reason_codes=[ev.event_type for ev in events if ev.severity > 0.5][:5],
                observation_level="deep",
                restrictions=["no_new_secrets", "no_crown_jewel_access", "limited_egress"],
                expires_at=time.time() + SOT_TTL_SECONDS,
                renewable=True,
            )
            self.state.active_sot_id = sot.token_id
            self.state.transition_to(IsolationState.OBSERVATION)
            await self._publish(
                "cortex.obs.sot.issued",
                {
                    **sot.model_dump(),
                    "entity_id": self.state.entity_id,
                    "timestamp": time.time(),
                },
            )
            return
        if action in {"prepare_quarantine", "prepare_irreversible_containment"}:
            if action == "prepare_irreversible_containment" and not check_multi_source(events, min_sources=2):
                await self._act("issue_sot", events, False, None)
                return
            action_class = ActionClass.EXECUTE_WITH_APPROVAL if action == "prepare_quarantine" else ActionClass.IRREVERSIBLE
            envelope = RiskEnvelope(
                entity_id=self.state.entity_id,
                entity_type=self.state.entity_type,
                action=action,
                action_class=action_class,
                trust_score=self.state.current_score,
                threat_level=5 if action_class == ActionClass.IRREVERSIBLE else 4,
                evidence_count=len(events),
                strong_signal_count=sum(1 for ev in events if ev.severity > 0.6),
                distinct_sources=len({ev.source for ev in events}),
                blast_radius=int(os.getenv("CORTEX_ESTIMATED_BLAST_RADIUS", "0")),
                crown_jewels_exposed=bool(os.getenv("CORTEX_CROWN_JEWEL")),
                criticality="critical" if os.getenv("CORTEX_CROWN_JEWEL") else "normal",
                scopes=["admin:write"],
                environment=os.getenv("CORTEX_ENVIRONMENT", "preprod"),
                dependencies=self._dependency_snapshot,
            )
            if action_class == ActionClass.IRREVERSIBLE and block_irreversible_actions(envelope.dependencies):
                await self._publish(
                    "cortex.security.events",
                    {
                        "event_type": "irreversible_blocked_due_to_degraded_mode",
                        "entity_id": self.state.entity_id,
                        "timestamp": time.time(),
                    },
                )
                await self._act("issue_sot", events, False, None)
                return
            await self._local_isolation()
            self.state.transition_to(IsolationState.QUARANTINED)
            await self._publish(
                "cortex.agents.tasks.remediation",
                {
                    "task_id": f"{action}-{self.state.entity_id}-{int(time.time())}",
                    "type": action,
                    "entity_id": self.state.entity_id,
                    "entity_type": self.state.entity_type,
                    "trust_score": self.state.current_score,
                    "trigger_signals": [ev.event_type for ev in events if ev.severity > 0.7],
                    "hard_stop": hard_stop,
                    "hs_signal": hs_sig,
                    "risk_level": 5 if action == "prepare_irreversible_containment" else 4,
                    "requires_approval": True,
                    "execution_mode": "prepare",
                    "forensic_required": action == "prepare_irreversible_containment",
                },
            )

    async def handle_command(self, cmd: dict[str, Any]) -> None:
        cmd_type = cmd.get("type")
        if cmd_type == "issue_sot":
            await self._act("issue_sot", [], False, None)
        elif cmd_type == "quarantine":
            self.state.transition_to(IsolationState.QUARANTINED)
            await self._local_isolation()
        elif cmd_type == "restrict":
            self.state.transition_to(IsolationState.RESTRICTED)
        elif cmd_type == "restore":
            self.state.transition_to(IsolationState.RECOVERY_PENDING)
            self.state.transition_to(IsolationState.RESTORED)
            self.state.transition_to(IsolationState.FREE)
            self.state.active_sot_id = None
            self.state.current_score = 75.0

    async def _local_isolation(self) -> None:
        if platform.system() == "Linux":
            audit_ip = os.getenv("CORTEX_AUDIT_IP", "")
            os.system("iptables -P OUTPUT DROP 2>/dev/null || true")
            os.system("iptables -P INPUT DROP 2>/dev/null || true")
            if audit_ip:
                os.system(f"iptables -A OUTPUT -d {audit_ip} -p tcp --dport 8080 -j ACCEPT 2>/dev/null || true")
            os.system("iptables -A OUTPUT -p udp --dport 53 -j ACCEPT 2>/dev/null || true")

    def _detect_context(self) -> str:
        if os.getenv("CORTEX_CROWN_JEWEL"):
            return "crown_jewel_access"
        if os.getenv("CORTEX_PRODUCTION"):
            return "production_env"
        if os.getenv("CORTEX_PAYMENT"):
            return "payment_data"
        if os.getenv("CORTEX_IDENTITY_STORE"):
            return "identity_store"
        return "normal_resource"

    async def _watchdog_loop(self) -> None:
        try:
            import psutil as watchdog_psutil
        except ImportError:
            return
        my_pid = os.getpid()
        while self._running:
            try:
                proc = watchdog_psutil.Process(my_pid)
                if proc.status() in (watchdog_psutil.STATUS_ZOMBIE, watchdog_psutil.STATUS_DEAD, watchdog_psutil.STATUS_STOPPED):
                    os.system("iptables -P OUTPUT DROP 2>/dev/null || true")
                    await self.nats.publish(
                        "cortex.security.events",
                        json.dumps({
                            "event_type": "sentinel_tamper",
                            "entity_id": self.state.entity_id,
                            "timestamp": time.time(),
                        }).encode(),
                    )
            except Exception:
                pass
            await asyncio.sleep(5)
