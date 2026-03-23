from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from .engine import InsiderDecayStore
from .models import InsiderDecayResponse, InsiderEvaluationRequest, InsiderEvent


def _flag_enabled() -> bool:
    return os.getenv("INSIDER_DECAY_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


class AppState:
    def __init__(self) -> None:
        self.started = False
        self.requests = 0
        self.store = InsiderDecayStore()


def create_app() -> FastAPI:
    state = AppState()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state.started = True
        yield

    app = FastAPI(title="Cortex Insider Decay", version="0.1.0", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.insider = state

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live", "service": "cortex-insider-decay"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, object]:
        return {"status": "ready", "service": "cortex-insider-decay", "enabled": _flag_enabled()}

    @app.get("/health/startup")
    async def health_startup(response: Response) -> dict[str, str]:
        if not state.started:
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "started", "service": "cortex-insider-decay"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body = "\n".join(
            [
                "# HELP cortex_insider_decay_requests_total Number of insider decay evaluations.",
                "# TYPE cortex_insider_decay_requests_total counter",
                f"cortex_insider_decay_requests_total {state.requests}",
                "",
            ]
        )
        return Response(content=body, media_type="text/plain; version=0.0.4")

    @app.get("/version")
    async def version() -> dict[str, str]:
        return {"service": "cortex-insider-decay", "version": "0.1.0"}

    @app.post("/v1/insider/events")
    async def ingest_event(event: InsiderEvent) -> dict[str, str]:
        if not _flag_enabled():
            raise HTTPException(status_code=503, detail="insider_decay_disabled")
        state.store.ingest(event)
        return {"status": "stored", "trace_id": event.trace_id}

    @app.post("/v1/insider/evaluate", response_model=InsiderDecayResponse)
    async def evaluate(req: InsiderEvaluationRequest) -> InsiderDecayResponse:
        if not _flag_enabled():
            raise HTTPException(status_code=503, detail="insider_decay_disabled")
        state.requests += 1
        signal = state.store.evaluate(req)
        return InsiderDecayResponse(
            signal=signal,
            rationale=[
                "Insider decay remains cumulative and advisory.",
                "A single subtle deviation must not trigger a destructive action on its own.",
            ],
        )

    return app


app = create_app()
