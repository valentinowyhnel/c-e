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
from pydantic import BaseModel, ConfigDict, Field


ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]


class ApprovalAction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId", min_length=1)
    intent: str = Field(min_length=1)
    risk_level: int = Field(alias="riskLevel", ge=1, le=5)
    dry_run_required: bool = Field(alias="dryRunRequired")


class ApprovalRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    requestor_id: str = Field(min_length=1)
    actions: list[ApprovalAction] = Field(default_factory=list, min_length=1)
    reasoning: str = Field(min_length=1)
    risk_level: int = Field(ge=4, le=5)
    correlation_id: str = ""
    execution_mode: str = "prepare"
    capability_maturity: str = "beta"
    degraded_mode: bool = False
    risk_envelope: dict[str, object] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    comment: str | None = None
    reason: str | None = None


class ApprovalRecord(BaseModel):
    plan_id: str
    requestor_id: str
    actions: list[ApprovalAction]
    reasoning: str
    risk_level: int
    request_id: str
    created_at: float
    updated_at: float
    deadline_ts: float
    approvers_required: int
    approvals_received: int
    status: ApprovalStatus
    last_comment: str = ""
    last_reason: str = ""
    resolved_at: float | None = None
    correlation_id: str = ""
    execution_mode: str = "prepare"
    capability_maturity: str = "beta"
    degraded_mode: bool = False
    risk_envelope: dict[str, object] = Field(default_factory=dict)


requests: dict[str, ApprovalRecord] = {}
db_pool = None


def require_internal_api(request: Request) -> None:
    expected = os.getenv("CORTEX_INTERNAL_API_TOKEN", "").strip()
    if not expected:
        return
    if request.headers.get("x-cortex-internal-token", "") != expected:
        raise HTTPException(status_code=403, detail="internal_api_auth_required")


def now_ts() -> float:
    return time.time()


def maybe_expire(record: ApprovalRecord) -> ApprovalRecord:
    if record.status == "pending" and now_ts() > record.deadline_ts:
        record.status = "expired"
        record.updated_at = now_ts()
        record.resolved_at = record.updated_at
    return record


def normalize_record(record: ApprovalRecord) -> dict[str, object]:
    return record.model_dump(by_alias=True)


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
            CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                requestor_id TEXT NOT NULL,
                actions_json TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                risk_level INT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL,
                deadline_ts DOUBLE PRECISION NOT NULL,
                approvers_required INT NOT NULL,
                approvals_received INT NOT NULL,
                status TEXT NOT NULL,
                last_comment TEXT NOT NULL,
                last_reason TEXT NOT NULL,
                resolved_at DOUBLE PRECISION NULL,
                correlation_id TEXT NOT NULL DEFAULT '',
                execution_mode TEXT NOT NULL DEFAULT 'prepare',
                capability_maturity TEXT NOT NULL DEFAULT 'beta',
                degraded_mode BOOLEAN NOT NULL DEFAULT FALSE,
                risk_envelope_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        await conn.execute("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS correlation_id TEXT NOT NULL DEFAULT ''")
        await conn.execute("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS execution_mode TEXT NOT NULL DEFAULT 'prepare'")
        await conn.execute("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS capability_maturity TEXT NOT NULL DEFAULT 'beta'")
        await conn.execute("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS degraded_mode BOOLEAN NOT NULL DEFAULT FALSE")
        await conn.execute("ALTER TABLE approval_requests ADD COLUMN IF NOT EXISTS risk_envelope_json TEXT NOT NULL DEFAULT '{}'")


def row_to_record(row: asyncpg.Record) -> ApprovalRecord:
    return ApprovalRecord(
        plan_id=row["plan_id"],
        requestor_id=row["requestor_id"],
        actions=[ApprovalAction.model_validate(item) for item in json.loads(row["actions_json"])],
        reasoning=row["reasoning"],
        risk_level=row["risk_level"],
        request_id=row["request_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deadline_ts=row["deadline_ts"],
        approvers_required=row["approvers_required"],
        approvals_received=row["approvals_received"],
        status=row["status"],
        last_comment=row["last_comment"],
        last_reason=row["last_reason"],
        resolved_at=row["resolved_at"],
        correlation_id=row["correlation_id"],
        execution_mode=row["execution_mode"],
        capability_maturity=row["capability_maturity"],
        degraded_mode=row["degraded_mode"],
        risk_envelope=json.loads(row["risk_envelope_json"] or "{}"),
    )


async def persist(record: ApprovalRecord) -> None:
    if db_pool is None:
        requests[record.request_id] = record
        return
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO approval_requests (
                request_id, plan_id, requestor_id, actions_json, reasoning, risk_level,
                created_at, updated_at, deadline_ts, approvers_required, approvals_received,
                status, last_comment, last_reason, resolved_at, correlation_id,
                execution_mode, capability_maturity, degraded_mode, risk_envelope_json
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16,
                $17, $18, $19, $20
            )
            ON CONFLICT (request_id) DO UPDATE SET
                updated_at = EXCLUDED.updated_at,
                approvals_received = EXCLUDED.approvals_received,
                status = EXCLUDED.status,
                last_comment = EXCLUDED.last_comment,
                last_reason = EXCLUDED.last_reason,
                resolved_at = EXCLUDED.resolved_at,
                correlation_id = EXCLUDED.correlation_id,
                execution_mode = EXCLUDED.execution_mode,
                capability_maturity = EXCLUDED.capability_maturity,
                degraded_mode = EXCLUDED.degraded_mode,
                risk_envelope_json = EXCLUDED.risk_envelope_json
            """,
            record.request_id,
            record.plan_id,
            record.requestor_id,
            json.dumps([action.model_dump(by_alias=True) for action in record.actions]),
            record.reasoning,
            record.risk_level,
            record.created_at,
            record.updated_at,
            record.deadline_ts,
            record.approvers_required,
            record.approvals_received,
            record.status,
            record.last_comment,
            record.last_reason,
            record.resolved_at,
            record.correlation_id,
            record.execution_mode,
            record.capability_maturity,
            record.degraded_mode,
            json.dumps(record.risk_envelope),
        )


async def get_record_or_404(request_id: str) -> ApprovalRecord:
    if db_pool is None:
        record = requests.get(request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="request_not_found")
        record = maybe_expire(record)
        return record

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM approval_requests WHERE request_id = $1", request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    record = maybe_expire(row_to_record(row))
    await persist(record)
    return record


async def list_records(status: Literal["pending", "approved", "rejected", "expired", "all"]) -> list[ApprovalRecord]:
    if db_pool is None:
        records = [maybe_expire(record) for record in requests.values()]
        if status != "all":
            records = [record for record in records if record.status == status]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records

    query = "SELECT * FROM approval_requests"
    params: tuple[object, ...] = ()
    if status != "all":
        query += " WHERE status = $1"
        params = (status,)
    query += " ORDER BY created_at DESC"
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    records = [maybe_expire(row_to_record(row)) for row in rows]
    for record in records:
        await persist(record)
    return records


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


app = FastAPI(title="Cortex Approval", lifespan=lifespan)


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ok", "service": "cortex-approval"}


@app.post("/v1/approvals")
async def request_approval(request: ApprovalRequest, http_request: Request) -> dict[str, object]:
    require_internal_api(http_request)
    created_at = now_ts()
    record = ApprovalRecord(
        plan_id=request.plan_id,
        requestor_id=request.requestor_id,
        actions=request.actions,
        reasoning=request.reasoning,
        risk_level=request.risk_level,
        request_id=str(uuid.uuid4()),
        created_at=created_at,
        updated_at=created_at,
        deadline_ts=created_at + (15 * 60 if request.risk_level >= 5 else 30 * 60),
        approvers_required=2 if request.risk_level >= 5 else 1,
        approvals_received=0,
        status="pending",
        correlation_id=request.correlation_id,
        execution_mode=request.execution_mode,
        capability_maturity=request.capability_maturity,
        degraded_mode=request.degraded_mode,
        risk_envelope=request.risk_envelope,
    )
    await persist(record)
    return normalize_record(record)


@app.get("/v1/approvals")
async def list_approvals(
    request: Request,
    status: Literal["pending", "approved", "rejected", "expired", "all"] = Query(default="pending")
) -> list[dict[str, object]]:
    require_internal_api(request)
    records = await list_records(status)
    return [normalize_record(record) for record in records]


@app.get("/v1/approvals/{request_id}")
async def get_approval(request_id: str, request: Request) -> dict[str, object]:
    require_internal_api(request)
    return normalize_record(await get_record_or_404(request_id))


@app.post("/v1/approvals/{request_id}/approve")
async def approve_request(request_id: str, decision: ApprovalDecision, request: Request) -> dict[str, object]:
    require_internal_api(request)
    record = await get_record_or_404(request_id)
    if record.status != "pending":
        raise HTTPException(status_code=409, detail="request_not_pending")
    record.approvals_received += 1
    record.last_comment = decision.comment or ""
    record.updated_at = now_ts()
    if record.approvals_received >= record.approvers_required:
        record.status = "approved"
        record.resolved_at = record.updated_at
    await persist(record)
    return normalize_record(record)


@app.post("/v1/approvals/{request_id}/reject")
async def reject_request(request_id: str, decision: ApprovalDecision, request: Request) -> dict[str, object]:
    require_internal_api(request)
    record = await get_record_or_404(request_id)
    if record.status != "pending":
        raise HTTPException(status_code=409, detail="request_not_pending")
    record.status = "rejected"
    record.last_reason = decision.reason or ""
    record.updated_at = now_ts()
    record.resolved_at = record.updated_at
    await persist(record)
    return normalize_record(record)
