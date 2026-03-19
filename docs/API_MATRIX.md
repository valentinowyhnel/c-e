# Cortex API Matrix

## Verification note

- Last successful runtime API verification on local Kind: `2026-03-19`
- Last local code/API verification: `2026-03-19`
- Runtime revalidation in this session used explicit kubeconfig `tmp-kind-kubeconfig.yaml`

## cortex-auth

| Method | Path | Purpose | Success | Error Cases | Tested |
|---|---|---|---|---|---|
| `GET` | `/health` | Health probe | `200` | none | runtime |
| `POST` | `/v1/tokens/issue` | Issue CAP token | `200` | invalid JSON, missing subject/session/device/DPoP, invalid principal type, invalid trust score | unit + runtime planned |
| `POST` | `/v1/tokens/validate` | Validate CAP token | `200` | invalid JSON, missing token, invalid signature/token | unit + runtime planned |

## cortex-sync

| Method | Path | Purpose | Success | Error Cases | Tested |
|---|---|---|---|---|---|
| `GET` | `/health` | Health probe | `200` | none | runtime |
| `POST` | `/v1/sync/full` | Queue full sync | `202` | malformed optional body falls back to defaults | unit + runtime planned |
| `POST` | `/v1/sync/delta` | Queue delta sync | `202` | malformed optional body falls back to defaults | unit + runtime planned |
| `GET` | `/v1/sync/jobs/{jobID}` | Read sync job | `200` | job not found | unit + runtime planned |

## cortex-graph

| Method | Path | Purpose | Success | Error Cases | Tested |
|---|---|---|---|---|---|
| `GET` | `/health` | Health probe | `200` | none | runtime |
| `GET` | `/v1/graph/overview` | Overview nodes/edges | `200` | none | runtime |
| `GET` | `/v1/graph/entities/{entityID}` | Entity detail | `200` | entity not found | unit |
| `GET` | `/v1/graph/search?q=` | Search entities | `200` | missing query | unit |

## cortex-approval

| Method | Path | Purpose | Success | Error Cases | Tested |
|---|---|---|---|---|---|
| `GET` | `/readyz` | Health probe | `200` | none | runtime |
| `POST` | `/v1/approvals` | Create approval | `200` | invalid risk, empty actions, invalid payload, `401` when internal token enforced | unit + runtime |
| `GET` | `/v1/approvals` | List approvals | `200` | invalid filter rejected by validation, `401` when internal token enforced | unit + runtime |
| `GET` | `/v1/approvals/{requestID}` | Read approval | `200` | not found, `401` when internal token enforced | unit + runtime |
| `POST` | `/v1/approvals/{requestID}/approve` | Approve request | `200` | not found, not pending, `401` when internal token enforced | unit + runtime |
| `POST` | `/v1/approvals/{requestID}/reject` | Reject request | `200` | not found, not pending, `401` when internal token enforced | unit |

## cortex-audit

| Method | Path | Purpose | Success | Error Cases | Tested |
|---|---|---|---|---|---|
| `GET` | `/readyz` | Health probe | `200` | none | runtime |
| `POST` | `/v1/events` | Write immutable audit event | `200` | invalid decision/risk/payload, `401` when internal token enforced | unit + runtime |
| `GET` | `/v1/events` | List audit events | `200` | filter mismatch returns empty list, `401` when internal token enforced | unit + runtime |
| `GET` | `/v1/events/{eventID}` | Read audit event | `200` | not found, `401` when internal token enforced | unit |

## cortex-trust-engine

| Method | Path | Purpose | Success | Error Cases | Tested |
|---|---|---|---|---|---|
| `GET` | `/health` | Health probe | `200` | none | runtime |
| `POST` | `/trust/evaluate/v2` | Evaluate trust from structured evidence | `200` | malformed payload, `401` when internal token enforced | unit + runtime |
| `POST` | `/trust/sot/issue` | Issue Suspicion Observation Token | `200` | malformed payload, `401` when internal token enforced | unit + runtime |
| `POST` | `/trust/sot/{tokenID}/expire` | Expire active SOT | `200` | not found, `401` when internal token enforced | unit |
| `POST` | `/trust/sot/{tokenID}/revoke` | Revoke active SOT | `200` | not found, `401` when internal token enforced | unit |
| `POST` | `/trust/sot/{tokenID}/impact` | Compute SOT impact | `200` | not found, `401` when internal token enforced | unit |
| `GET` | `/trust/sot/{tokenID}` | Read SOT state | `200` | not found, `401` when internal token enforced | unit |
| `GET` | `/trust/profile/{entityID}` | Read trust profile | `200` | not found, `401` when internal token enforced | unit |

## cortex-console proxy routes

| Method | Path | Backend | Success | Tested |
|---|---|---|---|---|
| `GET` | `/api/health` | local | `200` | runtime |
| `GET` | `/api/dashboard` | obs-agent + approval + graph | `200` | runtime |
| `GET` | `/api/events` | audit | `200` | runtime |
| `GET` | `/api/graph/overview` | graph | `200` | runtime |
| `GET` | `/api/obs/feed` | obs-agent | `200` | runtime |
| `GET` | `/api/obs/health` | obs-agent | `200` | runtime |
| `GET` | `/api/approvals` | approval | `200` | runtime |
| `GET` | `/api/approvals/{requestID}` | approval | `200` | runtime |
| `POST` | `/api/approvals/{requestID}/approve` | approval | `200` | runtime |
| `POST` | `/api/approvals/{requestID}/reject` | approval | `200` | runtime |

## Internal auth notes

- Sensitive internal service routes authenticate with `x-cortex-internal-token` when `CORTEX_INTERNAL_API_TOKEN` is configured.
- Console API routes require `read:console` or `admin:write` for sensitive reads, and `admin:write` for sensitive writes.
- `cortex-mcp-server` debug routing requires `read:debug` or `admin:write`.
- In current docs, `401` and `403` should both be treated as acceptable deny responses depending on service implementation details.

## Runtime health verified on 2026-03-19

- `cortex-trust-engine` -> `200 /health`
- `cortex-mcp-server` -> `200 /health`
- `cortex-obs-agent` -> `200 /healthz`
- `cortex-audit` -> `200 /readyz`
- `cortex-approval` -> `200 /readyz`
- `cortex-console` -> `200 /api/health`
- `cortex-auth` -> `200 /health`
- `cortex-graph` -> `200 /health`
- `cortex-orchestrator` -> `200 /health`
- `cortex-gateway` -> `200 /health`
- `cortex-vllm` -> `200 /health`
- `bloodhound-ce` -> `200 /health`
