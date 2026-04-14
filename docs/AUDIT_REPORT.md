# Cortex — Audit Report (Phase 0)

**Date:** 2026-04-14
**Branch:** `claude/wizardly-kare`
**Audit scope:** structural + static; no runtime/pytest execution (dependencies not installed in the audit environment).
**Method:** file inventory, test-function counts via grep, `/health` endpoint grep, hardcoded-secret scan, `scripts/runtime/check-production-maturity.py` run.

---

## 1. Headline

- `check-production-maturity.py` output: **`production_maturity=blocked`** with **8 capability blockers**.
- **22 service directories** under `services/`: 13 Python FastAPI, 5 Go, 1 Next.js, 1 OPA policy library, 1 Python standalone subtree (`python/cortex-sentinel-machine`), plus `shared/cortex-core`.
- **151 test functions** total (132 in services, 19 at repo root).
- **0 of the 10 CPIP services** from the mission exist. **0 of the 5 additional Zero-Trust core services** (`cortex-decision-service`, `cortex-state-engine`, `directory-control-plane`, `directory-providers`, `cortex-mcp-directory-server`) exist.
- **No `packages/`, no `apps/`, no `helm/cortex-nats/`** — these are referenced in the mission but are not present.
- **Policies directory**: single `policies/base/deny_all.rego`. No SLO policy file yet, despite the mission referencing `policies/slo/enterprise-rssi-slo.json`.

---

## 2. Production-maturity blockers (authoritative)

Output from `python scripts/runtime/check-production-maturity.py`:

```
production_maturity=blocked
blocker:ad_destructive_writes=stubbed
blocker:ad_read_validations=preprod_ready
blocker:bloodhound_exposure_analysis=preprod_ready
blocker:decision_committee=beta
blocker:irreversible_containment=experimental
blocker:local_quarantine=beta
blocker:model_governance_writes=beta
blocker:sot_issue=preprod_ready
```

Interpretation — three categories:

| Severity | Blocker | Meaning |
|---|---|---|
| **Critical** | `ad_destructive_writes=stubbed` | AD writes are not implemented — only stubs. Gating production. |
| **Critical** | `irreversible_containment=experimental` | Containment flow is experimental; invariants 14–15 of the mission cannot be guaranteed. |
| **Needs promotion** | `ad_read_validations`, `bloodhound_exposure_analysis`, `sot_issue` | `preprod_ready` — one promotion step away from GA. |
| **Needs hardening** | `decision_committee`, `local_quarantine`, `model_governance_writes` | `beta` — functional but not GA-graded. |

These 8 blockers define the minimum fix set before any CPIP work is merged on top.

---

## 3. Existing services inventory

Legend: **Score** is a 0-10 maturity estimate based on (files × tests × `/health` × Dockerfile × Helm × mission-criticality). Scoring rubric at §7.

### 3.1 Python FastAPI services

| Service | .py | Tests | /health | Dockerfile | Helm | Score | Notes |
|---|---:|---:|:---:|:---:|:---:|---:|---|
| `cortex-sentinel` | 10 | 15 | ✓ | ✓ | ✓ | **8** | RL agent; NATS bridge; compat HTTP server on :8080. Most test coverage of the core set. |
| `cortex-mcp-server` | 12 | 13 | ✓ | ✓ | ✓ | **7** | MCP facade + router + plugins. Tests exist. No explicit fail-closed pattern visible by grep. |
| `cortex-trust-engine` | 4 | 9 | ✓ | ✓ | ✓ | **7** | Scorer + SoT + edge integration tests. Central to ZT. |
| `cortex-orchestrator` | 2 | 9 | ✓ | ✓ | − | **6** | Helm chart lives under `cortex-agents`; explicit `failure_mode_allow`-style reference found. |
| `cortex-approval` | 2 | 8 | − | ✓ | − | **6** | Tests cover hash + signature path; `/health` not present via grep. Mission requires it. |
| `cortex-edge-inference` | 5 | 6 | ✓ | ✓ | ✓ | **6** | |
| `cortex-agents` | 16 | 6 | − | ✓ | ✓ | **6** | Agents (decision, remediation, AD, signal export). 6 tests is low for 16 modules. No `/health`. |
| `cortex-audit` | 2 | 6 | − | ✓ | − | **5** | No `/health`; mission requires JetStream-signed events — needs verification. |
| `cortex-vllm` | 3 | 5 | ✓ | ✓ | ✓ | **5** | Thin; mission expects `/v1/route`, `/v1/models`, `/health` — `/v1/route` not yet confirmed. |
| `cortex-policy-engine` | 2 | 5 | − | − | − | **4** | Library only (no FastAPI app, no Dockerfile, no Helm). Mission treats it as a service. |
| `cortex-obs-agent` | 4 | 2 | ✓ | ✓ | − | **4** | |
| `cortex-priority-engine` | 4 | 2 | ✓ | ✓ | ✓ | **4** | |
| `cortex-insider-decay` | 4 | 2 | ✓ | ✓ | − | **4** | |
| `cortex-campaign-memory` | 4 | 2 | ✓ | ✓ | ✓ | **4** | |
| `cortex-admin-anomaly` | 4 | 2 | ✓ | ✓ | − | **4** | |

### 3.2 Go services

| Service | .go | Tests | Dockerfile | Helm | Score | Notes |
|---|---:|---:|:---:|:---:|---:|---|
| `cortex-auth` | 5 | 0 | ✓ | − | **3** | No tests. Packaged under `cortex-enforcement` helm chart. |
| `cortex-gateway` | 5 | 0 | ✓ | − | **3** | No tests. |
| `cortex-graph` | 3 | 0 | ✓ | − | **3** | No tests. |
| `cortex-sync` | 3 | 0 | ✓ | − | **3** | No tests. |
| `cortex-nats-bridge` | 1 | 0 | ✓ | − | **2** | Skeleton. |

**Systemic issue:** the 5 Go services have **0 test functions** total. `Makefile` has `golangci-lint` wiring but no `go test` coverage.

### 3.3 TypeScript / frontend

| Package | Notes | Score |
|---|---|---:|
| `services/cortex-console` | Next.js 14, standalone output. Single `package.json`. No test script. No `packages/` workspace exists. | **4** |

Mission references `apps/frontend`, `apps/api`, `packages/types`, `packages/aptse`, `packages/events`, `packages/trust`, `packages/ad-policy-engine` — **none of these exist**. Either the mission target diverges from reality, or a TS monorepo migration is implied. Needs product decision.

### 3.4 Standalone / supporting

| Component | .py | Tests | Score | Notes |
|---|---:|---:|---:|---|
| `services/python/cortex-sentinel-machine` | 53 | 40 | **8** | Largest, best-tested component: unit + integration + adversarial (poisoning, drift) + performance suites. gRPC server, NATS bus, WAL queue, policy signing/verifier, learning guard. Ports: gRPC 50061, observability 18080. |
| `shared/cortex-core` | lib | — | **6** | Modules: `contracts`, `degraded`, `maturity`, `messages`, `meta_decision`, `sot`, `state_machine`. No `pyproject.toml`. Installed via path deps presumably. |
| `cortex/` (repo-root library) | ML/RL code | 19 at repo-root `tests/` | **5** | `continuous_learning`, `meta_decision/`, `learning/`, `llm/`, `mcp/`, `training_pipeline.py`, `rl_sentinel.py`, `graph.py`. |

---

## 4. Mission-required but MISSING

### 4.1 CPIP (0 / 10 exist)

| Service | State |
|---|---|
| `services/cortex-signal-ingestion` | MISSING |
| `services/cortex-behavioral-baseline` | MISSING |
| `services/cortex-threat-prediction` | MISSING |
| `services/cortex-anomaly-anticipation` | MISSING |
| `services/cortex-peer-deviation` | MISSING |
| `services/cortex-prs` | MISSING |
| `services/cortex-adaptive-gate` | MISSING |
| `services/cortex-autonomous-containment` | MISSING |
| `services/cortex-identity-fabric` | MISSING |
| `services/cortex-learning-loop` | MISSING (partially present as `cortex/learning/` library) |

### 4.2 Additional Zero-Trust core services (0 / 5 exist)

| Service | State | Partial coverage today |
|---|---|---|
| `services/cortex-decision-service` | MISSING | Go `cortex-auth` + `cortex-gateway` provide some ext_authz path; no Python authoritative service. |
| `services/cortex-state-engine` | MISSING | No PostgreSQL-backed replayable state service. |
| `services/directory-control-plane` | MISSING | `cortex-agents/cortex_agents/ad/` provides ldap_client, kerberos_validator, drift_detector. |
| `services/directory-providers` | MISSING | |
| `services/cortex-mcp-directory-server` | MISSING | `cortex-mcp-server` exists but is generic. |
| `services/cortex-agent-trust` | MISSING | Trust engine exists; "trust-of-trust" layer does not. |

### 4.3 Infrastructure gaps

- **`helm/cortex-nats/`** — does not exist. NATS is inlined in `helm/cortex-agents/templates/nats.yaml` as a single pod; **not the 3-node cluster with JetStream + mTLS + per-account ACL** the mission requires.
- **JetStream streams** — `scripts/setup-nats-streams.py` exists; not inspected for CPIP streams (`SIGNALS`, `BASELINE`, `PRS`, `PREDICTION`, `CONTAINMENT`). Likely absent.
- **Policies** — `policies/` only contains `base/deny_all.rego`. No `policies/slo/enterprise-rssi-slo.json`, no `scripts/chaos/scenarios/*-chaos.json`.
- **TS monorepo** — `packages/` and `apps/` directories do not exist.

---

## 5. Security & hygiene findings

| Finding | Severity | Locations |
|---|---|---|
| Dev-only tokens committed (`sentinel-machine-dev-key-32-bytes!!`, `sentinel-observability-token`) in defaults | **Medium** | `services/python/cortex-sentinel-machine/app/config/settings.py` defaults. These are `os.getenv(..., "<dev-default>")` — safe if env is always set in prod, but mission invariant #6 forbids secrets-as-env-vars at all in prod. |
| No `replace-*` placeholder values found | Good | |
| No hardcoded `password=`, `api_key=` etc. outside test fixtures | Good | |
| `failure_mode_allow` not seen in any Helm template | **High** | Mission requires Envoy ext_authz `failure_mode_allow=false`. Needs explicit verification once Envoy config is added. |
| `/health` missing on 5 Python services (`approval`, `audit`, `agents`, `policy-engine` lib) | Medium | Per mission invariant, every core service needs `/health`. |
| Go services have **0 tests** | High | `cortex-auth`, `cortex-gateway`, `cortex-graph`, `cortex-sync`, `cortex-nats-bridge`. |
| Only 1 OPA policy committed (`deny_all.rego`) | High | Mission expects compiled ZT + AD policies. |

Note: full vulnerability scans (`pip-audit`, `npm audit`, `govulncheck`, `trivy`, `truffleHog`) were **not run** because the audit environment does not have the service dependencies installed. This must be done as a follow-up step before any production promotion claim can be made.

---

## 6. What actually works vs. mission claims

| Mission claim | Reality today |
|---|---|
| "Cortex is in production-readiness" | `production_maturity=blocked` — 8 blockers. |
| "7 sub-agents coordinated by Principal Engineer" | No such multi-agent harness visible in the repo. `cortex-agents` has `decision`, `remediation`, and `ad` agents, not seven. |
| "Inference p95 < 50 ms, F1 > 0.87" | No ML benchmarks committed. No evidence the anomaly model has been trained or evaluated. |
| "NATS cluster 3-node mTLS JetStream" | Single-replica inline NATS; no separate chart; no TLS secrets in the committed chart. |
| "Envoy ext_authz fail-closed" | Envoy chart present (`helm/cortex-enforcement/templates/envoy-deployment.yaml`) but `failure_mode_allow` not grepped. |
| "CPIP remplace AD" | No CPIP service exists. |

---

## 7. Scoring rubric (how the 0-10 numbers were built)

+2 service skeleton exists (pyproject/go.mod + main + Dockerfile)
+1 Helm chart packaged
+1 `/health` endpoint present
+2 ≥ 5 test functions
+1 ≥ 10 test functions
+1 documented config surface (settings.py / values.yaml)
+1 mission-critical-path relevance (trust, decision, audit, approval, sentinel)
+1 adversarial / integration tests present

Cap at 10; floor at 2 if only a skeleton exists.

---

## 8. Recommended next slices (ordered by risk reduction)

1. **Fix the 8 production-maturity blockers.** They are the canonical gate; everything downstream is moot otherwise. Start with `ad_destructive_writes` (stubbed → implemented with dry-run + approval) and `irreversible_containment` (experimental → reversible by design, SOC override window).
2. **Add `/health` to the 5 services that lack it** (`approval`, `audit`, `agents`, `orchestrator` HTTP, `policy-engine` if promoted to service). Cheap, required by mission, unblocks K8s probes.
3. **Write Go service tests.** Five Go services at 0 tests is the highest single-category test debt.
4. **Promote NATS to a dedicated chart** `helm/cortex-nats/` with the 3-node cluster + JetStream + mTLS ACLs. Create the 5 CPIP JetStream streams.
5. **Commit the missing policy files** — `policies/slo/enterprise-rssi-slo.json`, at least one OPA policy beyond `deny_all.rego`, and the two chaos scenario JSONs.
6. **Only then** add the CPIP service skeletons. Skeletons first, models second — the mission's F1 > 0.87 target is not a first-pass deliverable, it is a downstream milestone after the data plane works.

The mission's parallel-agent pattern (Alpha/Beta/Gamma/…) is attractive but premature: without the blockers in §2 fixed, parallel CPIP work will be built on sand.

---

## 9. Caveats

- This audit is **static**: `pytest`, `npm test`, `go test`, `helm lint`, `pip-audit` were **not executed** because the audit container does not have the services' dependencies installed. Claimed green tests ≠ actually green. A follow-up dynamic audit is required and will likely surface additional findings.
- Test counts are function-level (`def test_`), not parameterized-case-level — real executed-test counts may be higher.
- The three `dev-insecure` / `dev-default` strings in `cortex-sentinel-machine` defaults are safe **if and only if** production env always overrides them. This was not verified.
- "Score" is a rough estimator, not a release gate. It exists to rank where attention is scarcest.
