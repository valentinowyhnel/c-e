#!/bin/sh
set -eu
. "$(dirname "$0")/common.sh"

require_cmd terraform

terraform -chdir="${ROOT_DIR}/infra/terraform" init -backend=false >/dev/null
terraform -chdir="${ROOT_DIR}/infra/terraform" validate
write_json "${REPORT_DIR}/terraform.json" '{"status":"passed"}'
