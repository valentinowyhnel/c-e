import hashlib
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

try:
    import asyncpg
except ImportError:  # pragma: no cover - optional in unit-test environments
    asyncpg = None
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    principal_id: str = Field(min_length=1)
    principal_type: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    action: str = Field(min_length=1)
    decision: Literal["allow", "deny", "monitor", "step_up"] = "allow"
    reason: str = Field(min_length=1)
    risk_level: int = Field(default=1, ge=1, le=5)
    metadata: dict[str, object] = Field(default_factory=dict)
    correlation_id: str = ""
    action_class: str = ""
    execution_mode: str = "execute"
    capability_maturity: str = "beta"
    degraded_mode: bool = False


events: list[dict[str, object]] = []
db_pool = None


def require_internal_api(request: Request) -> None:
    expected = os.getenv("CORTEX_INTERNAL_API_TOKEN", "").strip()
    if not expected:
        return
    if request.headers.get("x-cortex-internal-token", "") != expected:
        raise HTTPException(status_code=403, detail="internal_api_auth_required")


def sign_event(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def ensure_db() -> None:
    global db_pool
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url or asyncpg is None:
        return
    if db_pool is None:
        db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=4)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                principal_id TEXT NOT NULL,
                principal_type TEXT NOT NULL,
                event_type TEXT NOT NULL,
                action TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                risk_level INT NOT NULL,
                metadata_json TEXT NOT NULL,
                correlation_id TEXT NOT NULL DEFAULT '',
                action_class TEXT NOT NULL DEFAULT '',
                execution_mode TEXT NOT NULL DEFAULT 'execute',
                capability_maturity TEXT NOT NULL DEFAULT 'beta',
                degraded_mode BOOLEAN NOT NULL DEFAULT FALSE,
                timestamp DOUBLE PRECISION NOT NULL,
                signature TEXT NOT NULL
            )
            """
        )
        await conn.execute("ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS correlation_id TEXT NOT NULL DEFAULT ''")
        await conn.execute("ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS action_class TEXT NOT NULL DEFAULT ''")
        await conn.execute("ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS execution_mode TEXT NOT NULL DEFAULT 'execute'")
        await conn.execute("ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS capability_maturity TEXT NOT NULL DEFAULT 'beta'")
        await conn.execute("ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS degraded_mode BOOLEAN NOT NULL DEFAULT FALSE")


def row_to_event(row: asyncpg.Record) -> dict[str, object]:
    return {
        "event_id": row["event_id"],
        "principal_id": row["principal_id"],
        "principal_type": row["principal_type"],
        "event_type": row["event_type"],
        "action": row["action"],
        "decision": row["decision"],
        "reason": row["reason"],
        "risk_level": row["risk_level"],
        "metadata": json.loads(row["metadata_json"]),
        "correlation_id": row["correlation_id"],
        "action_class": row["action_class"],
        "execution_mode": row["execution_mode"],
        "capability_maturity": row["capability_maturity"],
        "degraded_mode": row["degraded_mode"],
        "timestamp": row["timestamp"],
        "signature": row["signature"],
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_db()
    try:
        yield
    finally:
        global db_pool
        if db_pool is not None:
            await db_pool.close()
            db_pool = None


app = FastAPI(title="Cortex Audit", lifespan=lifespan)


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ok", "service": "cortex-audit"}


@app.post("/v1/events")
async def write_event(event: AuditEvent, request: Request) -> dict[str, object]:
    require_internal_api(request)
    payload = event.model_dump()
    payload["event_id"] = str(uuid.uuid4())
    payload["timestamp"] = time.time()
    payload["signature"] = sign_event(payload)
    if db_pool is None:
        events.append(payload)
    else:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, principal_id, principal_type, event_type, action,
                    decision, reason, risk_level, metadata_json, correlation_id,
                    action_class, execution_mode, capability_maturity, degraded_mode,
                    timestamp, signature
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                """,
                payload["event_id"],
                payload["principal_id"],
                payload["principal_type"],
                payload["event_type"],
                payload["action"],
                payload["decision"],
                payload["reason"],
                payload["risk_level"],
                json.dumps(payload["metadata"]),
                payload["correlation_id"],
                payload["action_class"],
                payload["execution_mode"],
                payload["capability_maturity"],
                payload["degraded_mode"],
                payload["timestamp"],
                payload["signature"],
            )
    return {"status": "recorded", "count": len(events), "event_id": payload["event_id"], "signature": payload["signature"]}


@app.get("/v1/events")
async def list_events(
    request: Request,
    limit: int = Query(default=30, ge=1, le=200),
    principal_id: str | None = None,
    event_type: str | None = None,
    decision: str | None = None,
    correlation_id: str | None = None,
    action_class: str | None = None,
) -> list[dict[str, object]]:
    require_internal_api(request)
    if db_pool is None:
        filtered = events
        if principal_id:
            filtered = [event for event in filtered if event["principal_id"] == principal_id]
        if event_type:
            filtered = [event for event in filtered if event["event_type"] == event_type]
        if decision:
            filtered = [event for event in filtered if event["decision"] == decision]
        if correlation_id:
            filtered = [event for event in filtered if event.get("correlation_id") == correlation_id]
        if action_class:
            filtered = [event for event in filtered if event.get("action_class") == action_class]
        return list(reversed(filtered))[:limit]

    clauses: list[str] = []
    params: list[object] = []
    if principal_id:
        params.append(principal_id)
        clauses.append(f"principal_id = ${len(params)}")
    if event_type:
        params.append(event_type)
        clauses.append(f"event_type = ${len(params)}")
    if decision:
        params.append(decision)
        clauses.append(f"decision = ${len(params)}")
    if correlation_id:
        params.append(correlation_id)
        clauses.append(f"correlation_id = ${len(params)}")
    if action_class:
        params.append(action_class)
        clauses.append(f"action_class = ${len(params)}")
    params.append(limit)
    query = "SELECT * FROM audit_events"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += f" ORDER BY timestamp DESC LIMIT ${len(params)}"
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [row_to_event(row) for row in rows]


@app.get("/v1/events/{event_id}")
async def get_event(event_id: str, request: Request) -> dict[str, object]:
    require_internal_api(request)
    if db_pool is None:
        for event in events:
            if event["event_id"] == event_id:
                return event
        raise HTTPException(status_code=404, detail="event_not_found")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM audit_events WHERE event_id = $1", event_id)
    if row is not None:
        return row_to_event(row)
    raise HTTPException(status_code=404, detail="event_not_found")
