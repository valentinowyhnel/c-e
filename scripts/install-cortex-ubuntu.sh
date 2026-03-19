#!/usr/bin/env bash
set -euo pipefail

PROFILE="${CORTEX_PROFILE:-max}"
SKIP_VLLM="${SKIP_VLLM:-0}"
SKIP_VALIDATION="${SKIP_VALIDATION:-0}"
REPO_DIR="${REPO_DIR:-$PWD}"

log() {
  printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERREUR: commande requise absente: $1" >&2
    exit 1
  fi
}

configure_vm_profile() {
  log "Profil Cortex: ${PROFILE}"
  case "$PROFILE" in
    standard)
      export SKIP_VLLM="${SKIP_VLLM:-1}"
      ;;
    max)
      ;;
    *)
      echo "ERREUR: CORTEX_PROFILE doit valoir standard ou max" >&2
      exit 1
      ;;
  esac
}

ensure_ubuntu() {
  if [ ! -f /etc/os-release ]; then
    echo "ERREUR: environnement Linux non detecte" >&2
    exit 1
  fi
  if ! grep -qi "ubuntu" /etc/os-release; then
    echo "ERREUR: ce script cible Ubuntu" >&2
    exit 1
  fi
}

install_base_packages() {
  log "Installation des paquets Ubuntu de base"
  sudo apt-get update
  sudo apt-get install -y \
    git curl wget jq ca-certificates gnupg lsb-release \
    apt-transport-https software-properties-common
}

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker deja installe"
    return
  fi
  log "Installation Docker"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "${SUDO_USER:-$USER}" || true
  echo "INFO: si docker est inaccessible apres ce script, reconnecte la session pour appliquer le groupe docker."
}

run_repo_script() {
  local script="$1"
  log "Execution ${script}"
  bash "$REPO_DIR/${script}"
}

post_install_hints() {
  cat <<'EOF'

Installation Cortex terminee.

Actions utiles:
1. Ouvrir la console:
   kubectl port-forward -n cortex-system svc/cortex-console 3000:3000
   puis http://127.0.0.1:3000

2. Suivre les pods:
   kubectl get pods -A

3. Suivre les logs critiques:
   kubectl logs -n cortex-system deployment/cortex-gateway --tail=100
   kubectl logs -n cortex-system deployment/cortex-obs-agent --tail=100
   kubectl logs -n cortex-system daemonset/cortex-sentinel-machine --tail=100

4. Relancer les validations:
   bash scripts/validate-sentinel-machine.sh
   bash scripts/validate-runtime-api.sh
EOF
}

show_evou_banner() {
  local width
  width="$(tput cols 2>/dev/null || echo 120)"
  local frames=$(( width > 20 ? width / 2 : 10 ))
  local delay="0.03"
  local banner='
██╗   ██╗██╗███████╗███╗   ██╗██╗   ██╗███████╗███╗   ██╗██╗   ██╗███████╗
██║   ██║██║██╔════╝████╗  ██║██║   ██║██╔════╝████╗  ██║██║   ██║██╔════╝
██║   ██║██║█████╗  ██╔██╗ ██║██║   ██║█████╗  ██╔██╗ ██║██║   ██║█████╗
╚██╗ ██╔╝██║██╔══╝  ██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║██║   ██║██╔══╝
 ╚████╔╝ ██║███████╗██║ ╚████║ ╚████╔╝ ███████╗██║ ╚████║╚██████╔╝███████╗
  ╚═══╝  ╚═╝╚══════╝╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝

██╗    ███╗   ███╗ ██████╗ ███╗   ██╗██████╗ ███████╗
██║    ████╗ ████║██╔═══██╗████╗  ██║██╔══██╗██╔════╝
██║    ██╔████╔██║██║   ██║██╔██╗ ██║██║  ██║█████╗
██║    ██║╚██╔╝██║██║   ██║██║╚██╗██║██║  ██║██╔══╝
███████╗██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██████╔╝███████╗
╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚══════╝

███████╗██╗   ██╗ ██████╗ ██╗   ██╗
██╔════╝██║   ██║██╔═══██╗██║   ██║
█████╗  ██║   ██║██║   ██║██║   ██║
██╔══╝  ╚██╗ ██╔╝██║   ██║██║   ██║
███████╗ ╚████╔╝ ╚██████╔╝╚██████╔╝
╚══════╝  ╚═══╝   ╚═════╝  ╚═════╝
'

  printf '\n'
  for step in $(seq 0 "$frames"); do
    printf '\033[2J\033[H'
    printf '%*s' "$step" ''
    printf '%s\n' "$banner"
    sleep "$delay"
  done
  printf '\033[0m\n'
}

main() {
  ensure_ubuntu
  configure_vm_profile
  install_base_packages
  install_docker_if_needed

  cd "$REPO_DIR"
  require_cmd git

  run_repo_script "scripts/setup-env.sh"

  export PATH="$HOME/.local/bin:/usr/local/go/bin:$HOME/go/bin:$PATH"

  require_cmd docker
  require_cmd kubectl
  require_cmd helm
  require_cmd kind

  run_repo_script "scripts/setup-cluster.sh"
  run_repo_script "scripts/setup-vault.sh"
  run_repo_script "scripts/setup-spire.sh"
  run_repo_script "scripts/setup-identity.sh"
  run_repo_script "scripts/setup-enforcement.sh"
  run_repo_script "scripts/setup-observability.sh"
  run_repo_script "scripts/setup-agents.sh"
  run_repo_script "scripts/setup-immune-v2.sh"
  run_repo_script "scripts/setup-console.sh"

  if [ "$SKIP_VLLM" != "1" ]; then
    run_repo_script "scripts/deploy-vllm.sh"
  else
    log "Deploiement vLLM ignore"
  fi

  log "Initialisation des streams NATS"
  python3 "$REPO_DIR/scripts/setup-nats-streams.py"

  if [ "$SKIP_VALIDATION" != "1" ]; then
    run_repo_script "scripts/validate-sentinel-machine.sh"
    run_repo_script "scripts/validate-runtime-api.sh"
  else
    log "Validation finale ignoree"
  fi

  post_install_hints
  show_evou_banner
}

main "$@"
