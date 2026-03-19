#!/usr/bin/env bash
set -euo pipefail

RUNNER_VERSION="${RUNNER_VERSION:-2.332.0}"
RUNNER_USER="${RUNNER_USER:-github-runner}"
RUNNER_DIR="${RUNNER_DIR:-/opt/actions-runner}"
RUNNER_ARCHIVE="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_ARCHIVE}"
RUNNER_SHA256="${RUNNER_SHA256:-f2094522a6b9afeab07ffb586d1eb3f190b6457074282796c497ce7dce9e0f2a}"
ENV_DIR="${ENV_DIR:-/etc/github-runner}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo apt-get update
sudo apt-get install -y curl jq tar unzip ca-certificates openssl

if ! id -u "${RUNNER_USER}" >/dev/null 2>&1; then
  sudo useradd --system --create-home --home-dir "/home/${RUNNER_USER}" --shell /bin/bash "${RUNNER_USER}"
fi

sudo mkdir -p "${RUNNER_DIR}" "${ENV_DIR}"
sudo chown -R "${RUNNER_USER}:${RUNNER_USER}" "${RUNNER_DIR}"
sudo chmod 700 "${ENV_DIR}"

cd "${RUNNER_DIR}"
sudo -u "${RUNNER_USER}" curl -fsSL -o "${RUNNER_ARCHIVE}" "${RUNNER_URL}"
echo "${RUNNER_SHA256}  ${RUNNER_ARCHIVE}" | sha256sum -c
sudo -u "${RUNNER_USER}" tar xzf "${RUNNER_ARCHIVE}"
sudo ./bin/installdependencies.sh

sudo install -m 0755 "${SCRIPT_DIR}/bootstrap-ephemeral-runner.sh" /usr/local/bin/github-runner-bootstrap
sudo install -m 0644 "${SCRIPT_DIR}/github-runner.service" /etc/systemd/system/github-runner.service

sudo systemctl daemon-reload
echo "Installation terminee. Configure /etc/github-runner/runner.env et /etc/github-runner/app.pem puis lance:"
echo "  sudo systemctl enable --now github-runner.service"
