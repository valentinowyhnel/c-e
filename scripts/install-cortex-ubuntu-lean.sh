#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$PWD}"
CLEANUP_MODE="${CLEANUP_MODE:-dry-run}"
RESET_CLUSTER="${RESET_CLUSTER:-1}"
START_FRONTEND_PORT_FORWARD="${START_FRONTEND_PORT_FORWARD:-1}"
SKIP_VALIDATION="${SKIP_VALIDATION:-0}"
ENABLE_VLLM="${ENABLE_VLLM:-auto}"

KEEP_BROWSER_REGEX='^(firefox|chromium|google-chrome)$'
PURGE_APT_PATTERNS=(
  thunderbird
  libreoffice-common
  libreoffice-core
  libreoffice-*
  remmina
  transmission-gtk
  transmission-common
  rhythmbox
  shotwell
  cheese
  hexchat
)
DISABLE_SERVICES=(
  apache2
  nginx
  mysql
  mariadb
  postgresql
  redis-server
  mongod
  elasticsearch
  cups
  avahi-daemon
  bluetooth
)

log() {
  printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"
}

run_cleanup_cmd() {
  local cmd="$1"
  if [ "${CLEANUP_MODE}" = "apply" ]; then
    eval "${cmd}"
  else
    printf 'DRY-RUN %s\n' "${cmd}"
  fi
}

ensure_ubuntu() {
  if [ ! -f /etc/os-release ] || ! grep -qi ubuntu /etc/os-release; then
    echo "ERREUR: ce script cible Ubuntu." >&2
    exit 1
  fi
}

check_vm_budget() {
  local mem_mb cpus disk_gb
  mem_mb="$(free -m | awk '/^Mem:/ {print $2}')"
  cpus="$(nproc)"
  disk_gb="$(df -BG / | awk 'NR==2 {gsub(/G/, "", $4); print $4}')"

  log "VM detectee: RAM=${mem_mb}Mi CPU=${cpus} DISQUE_LIBRE=${disk_gb}Gi"
  if [ "${mem_mb}" -lt 7600 ]; then
    echo "ERREUR: moins de 7.6 Go de RAM detectes. Cortex ne sera pas stable." >&2
    exit 1
  fi
  if [ "${cpus}" -lt 4 ]; then
    echo "ERREUR: au moins 4 CPU requis." >&2
    exit 1
  fi
  if [ "${disk_gb}" -lt 80 ]; then
    echo "ERREUR: au moins 80 Go libres recommandes." >&2
    exit 1
  fi
}

install_base() {
  log "Installation des prerequis Ubuntu"
  sudo apt-get update
  sudo apt-get install -y \
    git curl wget jq ca-certificates gnupg lsb-release \
    apt-transport-https software-properties-common
}

cleanup_host() {
  log "Nettoyage hote Cortex (${CLEANUP_MODE})"
  log "Rappel: le script ne supprime PAS arbitrairement tout Ubuntu. Il applique un nettoyage controle et reversible autant que possible."

  for service in "${DISABLE_SERVICES[@]}"; do
    run_cleanup_cmd "sudo systemctl stop ${service} 2>/dev/null || true"
    run_cleanup_cmd "sudo systemctl disable ${service} 2>/dev/null || true"
  done

  for pattern in "${PURGE_APT_PATTERNS[@]}"; do
    run_cleanup_cmd "sudo apt-get purge -y '${pattern}' 2>/dev/null || true"
  done

  if command -v snap >/dev/null 2>&1; then
    while IFS= read -r snap_name; do
      [ -z "${snap_name}" ] && continue
      if [[ ! "${snap_name}" =~ ${KEEP_BROWSER_REGEX} ]] && [[ "${snap_name}" != "bare" ]] && [[ "${snap_name}" != "core20" ]] && [[ "${snap_name}" != "core22" ]] && [[ "${snap_name}" != "gtk-common-themes" ]]; then
        run_cleanup_cmd "sudo snap remove '${snap_name}' || true"
      fi
    done < <(snap list | awk 'NR>1 {print $1}')
  fi

  run_cleanup_cmd "docker system prune -af --volumes 2>/dev/null || true"
  run_cleanup_cmd "sudo apt-get autoremove -y"
  run_cleanup_cmd "sudo apt-get clean"
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker deja present"
    return
  fi
  log "Installation Docker"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "${SUDO_USER:-$USER}" || true
}

reset_cortex_state() {
  log "Reset de l'environnement Cortex"

  if [ "${RESET_CLUSTER}" = "1" ] && command -v kind >/dev/null 2>&1; then
    kind delete cluster --name cortex-dev || true
  fi

  docker ps -a --format '{{.ID}} {{.Names}}' | awk '/cortex|kindest/ {print $1}' | xargs -r docker rm -f || true
  docker images --format '{{.Repository}}:{{.Tag}}' | awk '/^cortex\// {print $1}' | xargs -r docker rmi -f || true
}

run_repo_script() {
  local script="$1"
  log "Execution ${script}"
  bash "${REPO_DIR}/${script}"
}

should_deploy_vllm() {
  local mem_mb
  mem_mb="$(free -m | awk '/^Mem:/ {print $2}')"
  case "${ENABLE_VLLM}" in
    1|true|yes)
      return 0
      ;;
    0|false|no)
      return 1
      ;;
    auto)
      [ "${mem_mb}" -ge 10000 ]
      return
      ;;
    *)
      echo "ERREUR: ENABLE_VLLM doit valoir auto, 1 ou 0" >&2
      exit 1
      ;;
  esac
}

start_frontend_last() {
  if [ "${START_FRONTEND_PORT_FORWARD}" != "1" ]; then
    return
  fi

  pkill -f "kubectl port-forward -n cortex-system svc/cortex-console 3000:3000" 2>/dev/null || true
  nohup kubectl port-forward -n cortex-system svc/cortex-console 3000:3000 >/tmp/cortex-console-port-forward.log 2>&1 &
  sleep 3
  log "Frontend disponible sur http://127.0.0.1:3000"
}

post_install_report() {
  cat <<EOF

Installation lean Cortex terminee.

- Cleanup mode: ${CLEANUP_MODE}
- Cluster reset: ${RESET_CLUSTER}
- Validation: ${SKIP_VALIDATION}
- vLLM: ${ENABLE_VLLM}

Commandes utiles:
  kubectl get pods -A
  kubectl get svc -n cortex-system
  kubectl logs -n cortex-system deployment/cortex-gateway --tail=100
  kubectl logs -n cortex-system deployment/cortex-console --tail=100

Si le port-forward frontend est actif:
  http://127.0.0.1:3000
EOF
}

main() {
  ensure_ubuntu
  check_vm_budget
  install_base
  cleanup_host
  install_docker

  cd "${REPO_DIR}"

  run_repo_script "scripts/setup-env.sh"
  export PATH="$HOME/.local/bin:/usr/local/go/bin:$HOME/go/bin:$PATH"

  reset_cortex_state

  run_repo_script "scripts/setup-cluster.sh"
  run_repo_script "scripts/setup-vault.sh"
  run_repo_script "scripts/setup-spire.sh"
  run_repo_script "scripts/setup-identity.sh"

  if should_deploy_vllm; then
    export SKIP_VLLM=0
    log "vLLM active pour cette machine"
  else
    export SKIP_VLLM=1
    log "vLLM desactive: machine trop contrainte pour un deploiement stable"
  fi

  # Backend control plane first.
  run_repo_script "scripts/setup-enforcement.sh"
  run_repo_script "scripts/setup-observability.sh"
  run_repo_script "scripts/setup-agents.sh"
  run_repo_script "scripts/setup-immune-v2.sh"

  log "Initialisation des streams NATS"
  python3 "${REPO_DIR}/scripts/setup-nats-streams.py"

  if [ "${SKIP_VALIDATION}" != "1" ]; then
    run_repo_script "scripts/validate-sentinel-machine.sh"
    run_repo_script "scripts/validate-runtime-api.sh"
  fi

  # Frontend last, once backend is stable.
  run_repo_script "scripts/setup-console.sh"
  start_frontend_last
  post_install_report
}

main "$@"
