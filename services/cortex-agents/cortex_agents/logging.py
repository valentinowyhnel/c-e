from __future__ import annotations

import logging

try:
    import structlog
except ImportError:  # pragma: no cover - optional dependency fallback
    structlog = None


def get_logger(name: str):
    if structlog is not None:
        return structlog.get_logger(name)
    return logging.getLogger(name)
