#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd helm kubectl

helm upgrade --install "${HELM_RELEASE_NAME}-staging" "${ROOT_DIR}/helm/cortex-infra" \
  --namespace "${KUBE_NAMESPACE}" \
  --create-namespace \
  --atomic \
  --dry-run=server

helm upgrade --install "${HELM_RELEASE_NAME}-staging" "${ROOT_DIR}/helm/cortex-infra" \
  --namespace "${KUBE_NAMESPACE}" \
  --create-namespace \
  --atomic

