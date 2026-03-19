import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentinel.collectors.psutil_col import CollectedEvent
from sentinel.engine import (
    CortexSentinelEngine,
    EntityState,
    IsolationState,
    check_multi_source,
    compute_score,
)


def ev(event_type, source, severity, confidence, age=5.0):
    return CollectedEvent(
        entity_id="test",
        timestamp=time.time() - age,
        source=source,
        event_type=event_type,
        severity=severity,
        confidence=confidence,
    )


class TestScore4D:
    def test_crown_jewel_amplifies_danger(self):
        state = EntityState("t", "machine")
        events = [ev("suspicious_process", "psutil_process", 0.8, 0.7)]
        s_normal, _, _, _ = compute_score(state, events, "normal_resource")
        s_crown, _, _, _ = compute_score(state, events, "crown_jewel_access")
        assert s_crown < s_normal

    def test_stale_signal_less_impact(self):
        state = EntityState("t", "machine")
        fresh = [ev("suspicious_process", "psutil_process", 0.8, 0.8, age=5)]
        stale = [ev("suspicious_process", "psutil_process", 0.8, 0.8, age=295)]
        s_fresh, _, _, _ = compute_score(state, fresh)
        s_stale, _, _, _ = compute_score(state, stale)
        assert s_stale > s_fresh

    def test_hard_stop_forces_zero(self):
        state = EntityState("t", "machine")
        event = ev("Credential Dump Attempt", "falco_rule", 0.95, 0.9)
        event.metadata = {"hard_stop": True}
        s, _, hs, _ = compute_score(state, [event])
        assert s == 0.0
        assert hs is True

    def test_protected_entity_action_is_alert_only(self):
        state = EntityState("dc-01", "machine", is_protected=True)
        events = [ev("suspicious_process", "psutil_process", 0.9, 0.9)]
        _, action, _, _ = compute_score(state, events)
        assert action == "alert_human_only"

    def test_recovery_slower_than_degradation(self):
        state = EntityState("t", "machine", current_score=50.0, baseline_score=50.0)
        danger = [ev("suspicious_process", "psutil_process", 0.8, 0.8)]
        recover = [ev("valid_cert", "psutil_process", 0.2, 0.8)]
        s_d, _, _, _ = compute_score(state, danger)
        s_r, _, _, _ = compute_score(state, recover)
        assert (50.0 - s_d) > (s_r - 50.0)

    def test_multi_source_requires_two_sources(self):
        same_source = [
            ev("lateral_move", "psutil_process", 0.9, 0.9),
            ev("cred_dump", "psutil_process", 0.85, 0.85),
        ]
        two_sources = [
            ev("lateral_move", "auditd_connect", 0.9, 0.9),
            ev("cred_dump", "falco_rule", 0.85, 0.85),
        ]
        assert check_multi_source(same_source) is False
        assert check_multi_source(two_sources) is True


class TestIsolationStateMachine:
    def test_free_cannot_jump_to_isolated(self):
        state = EntityState("t", "machine")
        ok = state.transition_to(IsolationState.ISOLATED)
        assert ok is False
        assert state.isolation_state == IsolationState.FREE

    def test_valid_chain(self):
        state = EntityState("t", "machine")
        assert state.transition_to(IsolationState.SUSPECTED)
        assert state.transition_to(IsolationState.OBSERVATION)
        assert state.transition_to(IsolationState.QUARANTINED)
        assert state.isolation_state == IsolationState.QUARANTINED

    def test_failed_is_terminal(self):
        state = EntityState("t", "machine", isolation_state=IsolationState.FAILED)
        for target in IsolationState:
            assert state.transition_to(target) is False


@pytest.mark.asyncio
async def test_sentinel_publishes_on_cycle():
    nc = AsyncMock()
    js = AsyncMock()
    nc.jetstream = MagicMock(return_value=js)
    engine = CortexSentinelEngine("node-01", "machine", nc)
    with patch.object(engine.collector, "collect", return_value=[ev("suspicious_process", "psutil_process", 0.7, 0.7)]):
        await engine._cycle()
    topics = [call.args[0] for call in js.publish.call_args_list]
    assert "cortex.obs.stream" in topics
    assert "cortex.trust.updates" in topics
