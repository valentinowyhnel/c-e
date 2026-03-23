from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from .engine import AdminBehaviorStore
from .models import AdminActionEvent, AdminCompromiseResponse, AdminSessionRequest


def _flag_enabled() -> bool:
    return os.getenv("ADMIN_COMPROMISE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


class AppState:
    def __init__(self) -> None:
        self.started = False
        self.store = AdminBehaviorStore()
        self.requests = 0


def create_app() -> FastAPI:
    state = AppState()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state.started = True
        yield

    app = FastAPI(title="Cortex Admin Anomaly", version="0.1.0", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.admin = state

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live", "service": "cortex-admin-anomaly"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, object]:
        return {"status": "ready", "service": "cortex-admin-anomaly", "enabled": _flag_enabled()}

    @app.get("/health/startup")
    async def health_startup(response: Response) -> dict[str, str]:
        if not state.started:
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "started", "service": "cortex-admin-anomaly"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body = "\n".join(
            [
                "# HELP cortex_admin_anomaly_requests_total Number of admin anomaly evaluations.",
                "# TYPE cortex_admin_anomaly_requests_total counter",
                f"cortex_admin_anomaly_requests_total {state.requests}",
                "",
            ]
        )
        return Response(content=body, media_type="text/plain; version=0.0.4")

    @app.get("/version")
    async def version() -> dict[str, str]:
        return {"service": "cortex-admin-anomaly", "version": "0.1.0"}

    @app.post("/v1/admin/history")
    async def ingest_history(event: AdminActionEvent) -> dict[str, str]:
        if not _flag_enabled():
            raise HTTPException(status_code=503, detail="admin_compromise_disabled")
        state.store.ingest(event)
        return {"status": "stored", "trace_id": event.trace_id}

    @app.post("/v1/admin/evaluate", response_model=AdminCompromiseResponse)
    async def evaluate(req: AdminSessionRequest) -> AdminCompromiseResponse:
        if not _flag_enabled():
            raise HTTPException(status_code=503, detail="admin_compromise_disabled")
        state.requests += 1
        signal = state.store.admin_session_escalation_detector(req.admin_id, req.actions, req.trace_id, req.correlation_id)
        return AdminCompromiseResponse(
            signal=signal,
            rationale=[
                "Admin anomaly remains advisory and must be consumed by Trust and Policy.",
                "Causal breaks and rare action chains are treated as strong context, not autonomous execution authority.",
            ],
        )

    return app


app = create_app()
