# Runbook GitLab CI Cortex

## Objectif

Le pipeline GitLab CI Cortex est fail-closed. Toute regression securite, policy, supply chain, integrite modele ou verification post-deploiement doit bloquer le merge ou la promotion.

## Fichiers

- `.gitlab-ci.yml`
- `ci/infra.yml`
- `ci/services.yml`
- `ci/policies.yml`
- `ci/ml.yml`
- `ci/frontend.yml`
- `ci/release.yml`

## Stages

1. `preflight`
2. `validate`
3. `unit`
4. `security`
5. `policy`
6. `build`
7. `package`
8. `integration`
9. `ephemeral-env`
10. `e2e`
11. `resilience`
12. `ml-guard`
13. `supply-chain`
14. `deploy-staging`
15. `post-deploy-staging`
16. `deploy-prod-canary`
17. `post-deploy-prod`
18. `promote`

## Jobs bloquants critiques

- `check-no-plaintext-secrets`
- `check-spiffe-attestation`
- `check-ext-authz-fail-closed`
- `check-policy-regression`
- `check-model-integrity`
- `check-audit-chain`
- `check-trace-propagation`
- `check-canary-health`
- `check-rollback-readiness`

## Seuils configurables

- `OPA_COVERAGE_MIN`
- `MAX_ALLOWED_FPR`
- `EXT_AUTHZ_P99_MAX_MS`
- `TRUST_ENGINE_P99_MAX_MS`
- `MAX_CRITICAL_VULNERABILITIES`
- `MIN_SIGNED_ARTIFACTS_RATIO`

## Echec pipeline: conduite a tenir

### 1. `check-no-plaintext-secrets`

- Ouvrir `artifacts/reports/secrets.json`
- Supprimer ou rediger la valeur en clair
- Rejouer `make ci-preflight`

### 2. `check-spiffe-attestation`

- Ouvrir `artifacts/reports/spiffe-attestation.json`
- Corriger `scripts/register-spire-entries.sh` ou les `serviceAccountName`
- Verifier `helm/cortex-spire` et `helm/cortex-sentinel-machine`

### 3. `check-ext-authz-fail-closed`

- Ouvrir `artifacts/reports/ext-authz.json`
- Corriger `helm/cortex-enforcement/templates/envoy-configmap.yaml`
- Interdire `failure_mode_allow: true`
- Revalider le timeout p99

### 4. `check-policy-regression`

- Ouvrir `artifacts/reports/policy-regression.json`
- Ajouter ou corriger les tests Rego
- Remonter la couverture au-dessus de `OPA_COVERAGE_MIN`

### 5. `check-model-integrity`

- Ouvrir `artifacts/reports/model-integrity.json`
- Verifier schema, signature, `rollback_pointer`, `feature_schema_hash`
- Refuser toute promotion si le manifest est incomplet

### 6. `check-audit-chain`

- Ouvrir `artifacts/reports/audit-chain.json`
- Verifier persistance, correlation et endpoints `cortex-audit`
- Confirmer qu'aucune suppression destructive n'est introduite

### 7. `check-trace-propagation`

- Ouvrir `artifacts/reports/trace-propagation.json`
- Verifier `trace_id` dans proto, gateway, contracts et services

### 8. `check-canary-health`

- Ouvrir `artifacts/reports/canary-health.json`
- Si `ext_authz` ou `trust engine` depassent le p99 max: rollback
- Bloquer la promotion tant que le canary n'est pas sain

### 9. `check-rollback-readiness`

- Ouvrir `artifacts/reports/rollback-readiness.json`
- Confirmer la presence du chemin de rollback et du `rollback_pointer`
- Ne jamais promouvoir si ce job est rouge

## Rollback

1. Arreter la promotion.
2. Rejouer le chart precedent avec la revision connue.
3. Restaurer le modele champion reference par `rollback_pointer`.
4. Reexecuter `post-deploy` puis `check-canary-health`.
5. Auditer l'incident dans `cortex-audit`.

## Dry-run obligatoire

- Terraform: `scripts/ci/terraform_plan_dry_run.sh`
- Helm staging/prod: `scripts/ci/deploy_staging.sh`, `scripts/ci/deploy_prod_canary.sh`
- Aucun changement destructif ne doit etre execute sans plan ou `--dry-run=server`

