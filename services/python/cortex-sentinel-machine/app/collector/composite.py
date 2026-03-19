from __future__ import annotations

from app.collector.osquery import OSCollector
from app.collector.synthetic import SyntheticCollector
from app.config import RuntimeSettings
from app.models import RawEvent


class CompositeCollector:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.synthetic = SyntheticCollector(settings)
        self.os = OSCollector(settings)

    def collect(self) -> list[RawEvent]:
        events = self.os.collect()
        if events:
            return events
        return self.synthetic.collect()
