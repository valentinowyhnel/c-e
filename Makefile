.PHONY: dev setup-env cluster vault spire identity enforcement agents console observability lint test gate gate-api gate-final build clean status

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
