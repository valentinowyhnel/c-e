#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd terraform

mkdir -p "${ARTIFACT_DIR}/terraform"
terraform -chdir="${ROOT_DIR}/infra/terraform" init -backend=false >/dev/null
terraform -chdir="${ROOT_DIR}/infra/terraform" plan -lock=false -input=false -out="${ARTIFACT_DIR}/terraform/plan.tfplan"
write_json "${REPORT_DIR}/terraform-plan.json" '{"status":"passed","mode":"dry-run"}'

