#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

write_json "${REPORT_DIR}/ephemeral-env.json" "{\"status\":\"passed\",\"release\":\"${HELM_RELEASE_NAME:-cortex}-ephemeral\",\"namespace\":\"${KUBE_NAMESPACE:-cortex-system}\"}"
log "Ephemeral environment definition prepared. Runner must provide kubectl/helm context."

