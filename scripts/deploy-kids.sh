#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${REPO_DIR}/services/kids"
# The downloader only receives this service's content directory, never the Docker socket.
# Docker creates the host bind path on first use. No sudo or host Python install is needed.
if [[ ! -f "${SERVICE_DIR}/.env" ]]; then
    lan_ip="${KIDS_LAN_IP:-}"
    if [[ -z "${lan_ip}" && -r "${REPO_DIR}/services/jellyfin/.env" ]]; then
        lan_ip="$(sed -n 's/^JELLYFIN_LAN_IP=//p' "${REPO_DIR}/services/jellyfin/.env")"
    fi
    [[ -n "${lan_ip}" && "${lan_ip}" != "0.0.0.0" ]] || { echo "Set KIDS_LAN_IP to the server LAN address." >&2; exit 1; }
    printf 'KIDS_LAN_IP=%s\n' "${lan_ip}" > "${SERVICE_DIR}/.env"
fi
lan_ip="$(sed -n 's/^KIDS_LAN_IP=//p' "${SERVICE_DIR}/.env")"
[[ -n "${lan_ip}" && "${lan_ip}" != "0.0.0.0" && "${lan_ip}" != "127.0.0.1" ]] || { echo "Invalid kids LAN address." >&2; exit 1; }
ip -4 addr show | grep -Fq "inet ${lan_ip}/" || { echo "Kids LAN address is not assigned to this host." >&2; exit 1; }
docker run --rm --mount "type=bind,src=${SERVICE_DIR}/prepare-content.py,dst=/prepare.py,readonly" \
    -v /srv/homelab/media/kids:/content python:3.13-alpine python /prepare.py
docker compose -f "${SERVICE_DIR}/compose.yml" config --quiet
docker compose -f "${SERVICE_DIR}/compose.yml" up -d --wait --wait-timeout 120
lan_ip="$(sed -n 's/^KIDS_LAN_IP=//p' "${SERVICE_DIR}/.env")"
curl --fail --silent --show-error --output /dev/null "http://${lan_ip}:8092/"
curl --fail --silent --show-error --location --output /dev/null --retry 12 --retry-delay 2 \
    "http://${lan_ip}:8092/discover/"
echo "Kids hub ready at http://${lan_ip}:8092/"
