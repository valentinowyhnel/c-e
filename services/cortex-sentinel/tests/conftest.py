import time

import pytest

from sentinel.collectors.psutil_col import CollectedEvent


@pytest.fixture
def sample_event():
    return CollectedEvent(
        entity_id="test",
        timestamp=time.time(),
        source="psutil_process",
        event_type="suspicious_process",
        severity=0.7,
        confidence=0.7,
    )
