# GitLab CI PASS/FAIL Matrix

| Controle | Source | PASS | FAIL |
| --- | --- | --- | --- |
| Secrets en clair | `check-no-plaintext-secrets` | Aucun secret detecte | Merge bloque |
| SPIFFE/SPIRE | `check-spiffe-attestation` | IDs et service accounts coherents | Merge bloque |
| ext_authz fail-closed | `check-ext-authz-fail-closed` | Pas de `failure_mode_allow: true`, timeout <= seuil | Merge bloque |
| Policies OPA | `check-policy-regression` | Tests OPA presents, couverture >= seuil | Merge bloque |
| Integrite ML | `check-model-integrity` | Schema + signature + rollback presents | Promotion bloquee |
| FPR | `ml-fpr-gate` | `false_positive_rate_estimate` <= seuil | Promotion bloquee |
| Audit immuable | `check-audit-chain` | Chaine auditable et persistante | Merge bloque |
| Trace propagation | `check-trace-propagation` | `trace_id` porte de bout en bout | Merge bloque |
| SBOM | `generate-sbom` | SBOM genere pour chaque image | Release bloquee |
| Signatures OCI | `verify-signed-artifacts` | Ratio signe = 100% | Release bloquee |
| Canary | `check-canary-health` | Canary sain et p99 conformes | Promotion bloquee |
| Rollback | `check-rollback-readiness` | Rollback pret et verifiable | Promotion bloquee |

## Seuils

- `OPA_COVERAGE_MIN`: minimum de couverture Rego
- `MAX_ALLOWED_FPR`: FPR maximum des modeles
- `EXT_AUTHZ_P99_MAX_MS`: latence p99 ext_authz maximum
- `TRUST_ENGINE_P99_MAX_MS`: latence p99 trust engine maximum
- `MAX_CRITICAL_VULNERABILITIES`: nombre maximal de CVE critiques
- `MIN_SIGNED_ARTIFACTS_RATIO`: ratio minimal d'artefacts signes

## Conditions de promotion

- Tous les stages precedents verts
- `deploy-staging` et `post-deploy-staging` verts
- `deploy-prod-canary` vert
- `check-canary-health` vert
- `check-rollback-readiness` vert
- `promote` execute sans erreur
