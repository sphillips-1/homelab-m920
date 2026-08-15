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

if [[ ! -f "${service_dir}/compose.yml" ]]; then
    echo "Skipping cloudflared: no Compose file found."
    return
fi

if [[ ! -f "${runtime_config}" ]]; then
    echo "Skipping cloudflared: ${runtime_config} has not been created."
    echo "Run sudo bash ${REPO_DIR}/scripts/configure-cloudflared.sh --mode safe first."
    return
fi

log "Deploying cloudflared"
cd "${service_dir}"
docker compose up -d --remove-orphans
echo "Service 'cloudflared' deployed."
}

deploy_service "audiobookshelf"
deploy_service "calibre-web"
deploy_service "homepage"
deploy_service "monitoring"
deploy_cloudflared

log "Service deployment complete"

echo
echo "Running containers:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
