#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-/etc/github-runner/runner.env}"
APP_KEY_PATH="${APP_KEY_PATH:-/etc/github-runner/app.pem}"

if [ ! -f "${ENV_FILE}" ]; then
  echo "ERREUR: fichier d'environnement introuvable: ${ENV_FILE}" >&2
  exit 1
fi

if [ ! -f "${APP_KEY_PATH}" ]; then
  echo "ERREUR: cle GitHub App introuvable: ${APP_KEY_PATH}" >&2
  exit 1
fi

source "${ENV_FILE}"

: "${GITHUB_APP_ID:?GITHUB_APP_ID requis}"
: "${GITHUB_INSTALLATION_ID:?GITHUB_INSTALLATION_ID requis}"
: "${GITHUB_OWNER:?GITHUB_OWNER requis}"
: "${GITHUB_REPO:?GITHUB_REPO requis}"
: "${RUNNER_NAME:?RUNNER_NAME requis}"
: "${RUNNER_LABELS:?RUNNER_LABELS requis}"
: "${RUNNER_WORKDIR:?RUNNER_WORKDIR requis}"

jwt_b64() {
  openssl base64 -A | tr '+/' '-_' | tr -d '='
}

issue_app_jwt() {
  local now iat exp header payload header_b64 payload_b64 unsigned signature
  now="$(date +%s)"
  iat="$((now - 60))"
  exp="$((now + 540))"
  header='{"alg":"RS256","typ":"JWT"}'
  payload="{\"iat\":${iat},\"exp\":${exp},\"iss\":\"${GITHUB_APP_ID}\"}"

  header_b64="$(printf '%s' "${header}" | jwt_b64)"
  payload_b64="$(printf '%s' "${payload}" | jwt_b64)"
  unsigned="${header_b64}.${payload_b64}"
  signature="$(printf '%s' "${unsigned}" | openssl dgst -sha256 -sign "${APP_KEY_PATH}" | jwt_b64)"
  printf '%s.%s' "${unsigned}" "${signature}"
}

github_api() {
  local method="$1"
  local url="$2"
  local auth="$3"
  curl -fsSL -X "${method}" \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${auth}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${url}"
}

APP_JWT="$(issue_app_jwt)"
INSTALL_TOKEN="$(
  github_api POST "https://api.github.com/app/installations/${GITHUB_INSTALLATION_ID}/access_tokens" "${APP_JWT}" \
    | jq -r '.token'
)"

REG_TOKEN="$(
  github_api POST "https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/runners/registration-token" "${INSTALL_TOKEN}" \
    | jq -r '.token'
)"

if [ -z "${REG_TOKEN}" ] || [ "${REG_TOKEN}" = "null" ]; then
  echo "ERREUR: token d'enregistrement GitHub Actions vide" >&2
  exit 1
fi

mkdir -p "${RUNNER_WORKDIR}"
cd "${RUNNER_WORKDIR}"

if [ ! -x "./config.sh" ] || [ ! -x "./run.sh" ]; then
  echo "ERREUR: runner GitHub non installe dans ${RUNNER_WORKDIR}" >&2
  exit 1
fi

if [ ! -f .runner ]; then
  sudo -u github-runner ./config.sh \
    --url "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}" \
    --token "${REG_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --work "_work" \
    --unattended \
    --replace \
    --ephemeral
fi

exec sudo -u github-runner ./run.sh
