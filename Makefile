.PHONY: dev setup-env cluster vault spire identity enforcement agents console observability lint test gate gate-api gate-final build clean status ci-preflight ci-validate ci-unit ci-security ci-policy ci-build ci-package ci-integration ci-ephemeral-env ci-e2e ci-resilience ci-ml-guard ci-supply-chain ci-deploy-staging ci-post-deploy-staging ci-deploy-prod-canary ci-post-deploy-prod ci-promote

dev: cluster vault spire
	@echo "Environnement Cortex pret. Lance 'make status' pour verifier."

setup-env:
	@bash scripts/setup-env.sh

cluster:
	@bash scripts/setup-cluster.sh

vault:
	@bash scripts/setup-vault.sh

spire:
	@bash scripts/setup-spire.sh

identity:
	@bash scripts/setup-identity.sh

enforcement:
	@bash scripts/setup-enforcement.sh

agents:
	@bash scripts/setup-agents.sh

console:
	@bash scripts/setup-console.sh

observability:
	@bash scripts/setup-observability.sh

lint:
	@echo "=== Lint Go services ==="
	@for d in services/cortex-auth services/cortex-policy \
	           services/cortex-graph services/cortex-gateway \
	           services/cortex-sync; do \
	  [ -f "$$d/go.mod" ] && (cd $$d && golangci-lint run ./...) || true; \
	done
	@echo "=== Lint Python services ==="
	@for d in services/cortex-trust-engine services/cortex-mcp-server \
	           services/cortex-orchestrator services/cortex-agents \
	           services/cortex-sentinel services/cortex-vllm \
	           services/cortex-approval; do \
	  [ -f "$$d/pyproject.toml" ] && (cd $$d && ruff check . && mypy .) || true; \
	done
	@echo "=== Lint Helm charts ==="
	@for c in helm/cortex-*/; do [ -d "$$c" ] && helm lint "$$c" --strict || true; done
	@echo "=== Lint OPA policies ==="
	@opa test policies/ -v

test:
	@for d in services/cortex-*/; do \
	  if [ -f "$$d/go.mod" ]; then (cd $$d && go test ./... -race); fi; \
	  if [ -f "$$d/pyproject.toml" ]; then (cd $$d && pytest -x); fi; \
	done

gate:
	@bash tests/security/current-gate.sh

gate-api:
	@bash tests/security/gate-api.sh

gate-final:
	@bash tests/security/gate-final.sh

build:
	@for d in services/cortex-*/; do \
	  [ -f "$$d/Dockerfile" ] && docker build -t cortex/$$(basename $$d):dev "$$d" || true; \
	done

ci-preflight:
	@bash scripts/ci/check_no_plaintext_secrets.sh

ci-validate:
	@sh scripts/ci/terraform_validate.sh
	@sh scripts/ci/terraform_plan_dry_run.sh
	@sh scripts/ci/helm_validate.sh
	@bash scripts/ci/check_spiffe_attestation.sh

ci-unit:
	@bash scripts/ci/run_go_tests.sh
	@bash scripts/ci/run_python_tests.sh
	@bash scripts/ci/run_frontend_checks.sh test

ci-security:
	@bash scripts/ci/check_ext_authz_fail_closed.sh
	@python scripts/ci/check_audit_chain.py
	@bash scripts/ci/check_trace_propagation.sh

ci-policy:
	@bash scripts/ci/run_policy_tests.sh
	@bash scripts/ci/check_policy_regression.sh

ci-build:
	@sh scripts/ci/build_images.sh
	@bash scripts/ci/run_frontend_checks.sh build

ci-package:
	@bash scripts/ci/package_services.sh
	@bash scripts/ci/package_models.sh

ci-integration:
	@bash scripts/ci/run_integration_suite.sh

ci-ephemeral-env:
	@bash scripts/ci/spawn_ephemeral_env.sh
	@helm template cortex-ci-smoke helm/cortex-ci-smoke >/dev/null

ci-e2e:
	@bash scripts/ci/run_e2e.sh

ci-resilience:
	@bash scripts/ci/run_resilience.sh

ci-ml-guard:
	@python scripts/ci/check_model_integrity.py
	@python scripts/ci/check_ml_metrics.py

ci-supply-chain:
	@python scripts/ci/verify_signed_artifacts.py

ci-deploy-staging:
	@bash scripts/ci/deploy_staging.sh

ci-post-deploy-staging:
	@bash scripts/ci/post_deploy_verify.sh staging

ci-deploy-prod-canary:
	@bash scripts/ci/deploy_prod_canary.sh

ci-post-deploy-prod:
	@bash scripts/ci/post_deploy_verify.sh production
	@bash scripts/ci/check_canary_health.sh
	@python scripts/ci/check_rollback_readiness.py

ci-promote:
	@bash scripts/ci/promote_release.sh

status:
	@echo "=== Nodes ==="
	@kubectl get nodes -o wide
	@echo "\n=== Pods Cortex ==="
	@kubectl get pods -n cortex-system
	@echo "\n=== Vault ==="
	@kubectl get pods -n vault-system
	@echo "\n=== SPIRE ==="
	@kubectl get pods -n spire-system
	@echo "\n=== RAM WSL2 ==="
	@free -h

clean:
	@kind delete cluster --name cortex-dev
	@echo "Cluster supprime."
