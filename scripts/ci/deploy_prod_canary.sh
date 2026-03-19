#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd helm kubectl

helm upgrade --install "${HELM_RELEASE_NAME}-prod" "${ROOT_DIR}/helm/cortex-infra" \
  --namespace "${KUBE_NAMESPACE}" \
  --atomic \
  --set rolloutStrategy=canary \
  --set canary.enabled=true \
  --dry-run=server

helm upgrade --install "${HELM_RELEASE_NAME}-prod" "${ROOT_DIR}/helm/cortex-infra" \
  --namespace "${KUBE_NAMESPACE}" \
  --atomic \
  --set rolloutStrategy=canary \
  --set canary.enabled=true

