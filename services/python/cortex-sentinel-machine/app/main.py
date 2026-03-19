from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from app.collector import CompositeCollector
from app.config import RuntimeSettings
from app.service import SentinelMachineService


def main() -> None:
    settings = RuntimeSettings()
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    Path("./var").mkdir(parents=True, exist_ok=True)
    service = SentinelMachineService(settings, CompositeCollector(settings))
    outcomes = service.process_once()
    print(json.dumps({"processed": len(outcomes), "health": asdict(service.health())}, sort_keys=True))


if __name__ == "__main__":
    main()
