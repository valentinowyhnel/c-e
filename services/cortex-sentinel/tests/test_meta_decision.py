from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sentinel.collectors.psutil_col import CollectedEvent
from sentinel.engine import CortexSentinelEngine


def ev(event_type, source, severity, confidence, age=5.0):
    return CollectedEvent(
        entity_id="node-01",
        timestamp=time.time() - age,
        source=source,
        event_type=event_type,
        severity=severity,
        confidence=confidence,
    )


def test_sentinel_meta_decision_can_downgrade_to_sot() -> None:
    async def run() -> None:
        nc = AsyncMock()
        js = AsyncMock()
        nc.jetstream = MagicMock(return_value=js)
        engine = CortexSentinelEngine("node-01", "machine", nc)
        engine.meta_decision.ingest_signal(
            {
                "entity_id": "node-01",
                "agent_id": "decision",
                "specialty": "response_decision",
                "risk_signal": 0.95,
                "runtime_trust": 0.42,
                "uncertainty": 0.55,
                "data_quality": 0.7,
                "reasoning_quality": 0.7,
            }
        )
        engine.meta_decision.ingest_signal(
            {
                "entity_id": "node-01",
                "agent_id": "remediation",
                "specialty": "containment_planning",
                "risk_signal": 0.1,
                "runtime_trust": 0.44,
                "uncertainty": 0.58,
                "data_quality": 0.7,
                "reasoning_quality": 0.68,
            }
        )
        with patch.object(engine.collector, "collect", return_value=[ev("suspicious_process", "falco_rule", 0.95, 0.95)]):
            await engine._cycle()
        topics = [call.args[0] for call in js.publish.call_args_list]
        assert "cortex.meta_decision.events" in topics
        trust_update_payload = next(call.args[1] for call in js.publish.call_args_list if call.args[0] == "cortex.trust.updates")
        assert b'"deep_analysis_triggered": true' in trust_update_payload

    asyncio.run(run())
