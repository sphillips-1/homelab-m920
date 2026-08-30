#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
SERVICES_DIR="${REPO_DIR}/services"

log() {
echo
echo "==> $1"
}

fail() {
echo "ERROR: $1" >&2
exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
fail "Run this script as root."
fi

if [[ ! -d "${SERVICES_DIR}" ]]; then
fail "Services directory not found: ${SERVICES_DIR}"
fi

if ! command -v docker >/dev/null 2>&1; then
fail "Docker is not installed."
fi

if ! docker compose version >/dev/null 2>&1; then
fail "Docker Compose plugin is not installed."
fi

log "Creating persistent directories"

"${REPO_DIR}/scripts/create-directories.sh"

log "Creating Audiobookshelf compatibility links"

"${REPO_DIR}/scripts/create-audiobook-links.sh"

log "Creating Docker network"

if ! docker network inspect homelab >/dev/null 2>&1; then
docker network create homelab
else
echo "Docker network 'homelab' already exists."
fi

deploy_service() {
local service="$1"
local service_dir="${SERVICES_DIR}/${service}"

if [[ ! -d "${service_dir}" ]]; then
    echo "Skipping ${service}: directory does not exist."
    return
fi

if [[ ! -f "${service_dir}/compose.yml" ]] &&
   [[ ! -f "${service_dir}/docker-compose.yml" ]]; then
    echo "Skipping ${service}: no Compose file found."
    return
fi

log "Deploying ${service}"

cd "${service_dir}"

docker compose up -d --remove-orphans

echo "Service '${service}' deployed."

}

deploy_cloudflared() {
local service_dir="${SERVICES_DIR}/cloudflared"
local runtime_config="/srv/homelab/appdata/cloudflared/config.yml"
local desired_mode_file="${REPO_DIR}/config/cloudflared/desired-mode"
local desired_mode
local rendered_config=false

if [[ ! -f "${service_dir}/compose.yml" ]]; then
    echo "Skipping cloudflared: no Compose file found."
    return
fi

if [[ ! -f "${runtime_config}" ]]; then
    echo "Skipping cloudflared: ${runtime_config} has not been created."
    echo "Run sudo bash ${REPO_DIR}/scripts/configure-cloudflared.sh --mode safe first."
    return
fi

if [[ -f "${desired_mode_file}" ]]; then
    desired_mode="$(tr -d '[:space:]' < "${desired_mode_file}")"
    case "${desired_mode}" in
        safe|sso)
            log "Rendering desired Cloudflare Tunnel mode: ${desired_mode}"
            bash "${REPO_DIR}/scripts/configure-cloudflared.sh" --mode "${desired_mode}"
            rendered_config=true
            ;;
        *)
            fail "Unsupported Cloudflare Tunnel desired mode: ${desired_mode}"
            ;;
    esac
fi

log "Deploying cloudflared"
cd "${service_dir}"
docker compose up -d --remove-orphans
if [[ "${rendered_config}" == true ]]; then
    docker compose restart cloudflared
fi
echo "Service 'cloudflared' deployed."
}

deploy_monitoring() {
local service_dir="${SERVICES_DIR}/monitoring"

if [[ ! -f "${service_dir}/compose.yml" ]]; then
    echo "Skipping monitoring: no Compose file found."
    return
fi

log "Deploying monitoring"
cd "${service_dir}"

if [[ -f "${service_dir}/.env" ]]; then
    docker compose --profile agent up -d --remove-orphans
    echo "Monitoring dashboard and container agent deployed."
else
    docker compose up -d --remove-orphans
    echo "Monitoring dashboard deployed without the agent."
    echo "Complete the one-time setup in ${service_dir}/README.md to enable container metrics."
fi
}

deploy_service "authentik"

# The provisioner source is bind-mounted read-only, so Compose does not detect
# Python-only changes as a reason to recreate the otherwise unchanged container.
# Restart it on deployment to load the checked-out server.py.
log "Reloading Authentik invitation provisioner"
docker compose -f "${SERVICES_DIR}/authentik/compose.yml" \
    restart invitation-provisioner

log "Reconciling Authentik invite creator"
docker exec -i authentik-worker ak shell \
    < "${REPO_DIR}/scripts/reconcile-invite-creator.py"

log "Reconciling Status SSO invitation access"
docker exec -i authentik-worker ak shell \
    < "${REPO_DIR}/scripts/reconcile-status-sso.py"

log "Reconciling Authentik Terraform CI permissions"
docker exec -i authentik-worker ak shell \
    < "${REPO_DIR}/scripts/reconcile-authentik-ci-permissions.py"

deploy_service "audiobookshelf"
deploy_service "calibre-web"
log "Configuring Jellyfin host-specific LAN and GPU values"
bash "${REPO_DIR}/scripts/configure-jellyfin-host.sh"
deploy_service "jellyfin"
log "Reconciling Jellyfin Intel Quick Sync transcoding"
bash "${REPO_DIR}/scripts/configure-jellyfin-transcoding.sh"
deploy_service "homepage"
deploy_monitoring
deploy_cloudflared

log "Service deployment complete"

echo
echo "Running containers:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
