import json
import tempfile
from pathlib import Path

from sentinel.collectors.auditd import AuditdCollector
from sentinel.collectors.falco import FalcoCollector
from sentinel.collectors.psutil_col import CollectedEvent, SentinelCollector


def test_auditd_parse_exec():
    collector = AuditdCollector()
    event = collector._parse("node,root,python -c import os", "node-1")
    assert event is not None
    assert event.entity_id == "node-1"


def test_falco_collect_reads_json_lines():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "events.json"
        path.write_text(json.dumps({"rule": "Credential Dump Attempt", "priority": "CRITICAL"}) + "\n", encoding="utf-8")
        collector = FalcoCollector(str(path))
        events = collector.collect("node-1")
        assert len(events) == 1
        assert events[0].metadata["hard_stop"] is True


def test_sentinel_dedup(sample_event: CollectedEvent):
    collector = SentinelCollector("node-1")
    duplicate = CollectedEvent(**{**sample_event.__dict__, "timestamp": sample_event.timestamp + 0.1})
    unique = collector._dedup([sample_event, duplicate])
    assert len(unique) == 1
