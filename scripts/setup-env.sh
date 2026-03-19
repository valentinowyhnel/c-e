#!/bin/bash
set -euo pipefail

echo "=== Cortex setup environnement WSL2 ==="

command -v docker >/dev/null 2>&1 || {
  echo "ERREUR: Docker non detecte. Installer Docker Desktop avec integration WSL2."
  exit 1
}

TOTAL_MEM=$(free -m | awk '/^Mem:/ {print $2}')
if [ "${TOTAL_MEM:-0}" -lt 6000 ]; then
  echo "AVERTISSEMENT: moins de 6 GiB de RAM detectes."
fi

sudo apt-get update -qq
sudo apt-get install -y -qq \
  jq curl wget gnupg lsb-release apt-transport-https \
  netcat-openbsd build-essential git unzip ca-certificates

sudo install -d -m 0755 /etc/apt/keyrings

if ! command -v kubectl >/dev/null 2>&1; then
  curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | \
    sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
  echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' | \
    sudo tee /etc/apt/sources.list.d/kubernetes.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq kubectl
fi

if ! command -v helm >/dev/null 2>&1; then
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

if ! command -v kind >/dev/null 2>&1; then
  curl -Lo /tmp/kind https://kind.sigs.k8s.io/dl/v0.22.0/kind-linux-amd64
  chmod +x /tmp/kind
  sudo mv /tmp/kind /usr/local/bin/kind
fi

if ! command -v terraform >/dev/null 2>&1 || ! command -v vault >/dev/null 2>&1; then
  wget -O- https://apt.releases.hashicorp.com/gpg | \
    sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
    sudo tee /etc/apt/sources.list.d/hashicorp.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq terraform vault
fi

if ! command -v go >/dev/null 2>&1; then
  GO_VERSION="1.22.3"
  curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" | sudo tar -C /usr/local -xzf -
fi

if ! grep -q '/usr/local/go/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo 'export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin' >> "$HOME/.bashrc"
fi
export PATH="$PATH:/usr/local/go/bin:$HOME/go/bin"

go install github.com/golangci/golangci-lint/cmd/golangci-lint@v1.57.2
go install github.com/cosmtrek/air@v1.51.0
go install golang.org/x/vuln/cmd/govulncheck@latest
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.33.0
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3.0
go install github.com/bufbuild/buf/cmd/buf@v1.30.0

if ! command -v uv >/dev/null 2>&1; then
  curl -fsSL https://astral.sh/uv/install.sh | sh
fi

if ! grep -q '$HOME/.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi
export PATH="$HOME/.local/bin:$PATH"

uv tool install ruff || true
uv tool install mypy || true

if ! command -v k9s >/dev/null 2>&1; then
  curl -sS https://webinstall.dev/k9s | bash
fi

if ! command -v opa >/dev/null 2>&1; then
  curl -L -o /tmp/opa https://openpolicyagent.org/downloads/v0.63.0/opa_linux_amd64_static
  chmod +x /tmp/opa
  sudo mv /tmp/opa /usr/local/bin/opa
fi

echo "=== Setup termine. Relance ton shell si necessaire: exec bash ==="
