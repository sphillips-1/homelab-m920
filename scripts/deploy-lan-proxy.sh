#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${REPO_DIR}/services/lan-proxy"
if [[ ! -f "${SERVICE_DIR}/.env" ]]; then
    lan_ip="${LAN_HTTP_IP:-$(sed -n 's/^KIDS_LAN_IP=//p' "${REPO_DIR}/services/kids/.env")}"
    [[ -n "${lan_ip}" ]] || { echo "Set LAN_HTTP_IP to the selected LAN address." >&2; exit 1; }
    printf 'LAN_HTTP_IP=%s\n' "${lan_ip}" > "${SERVICE_DIR}/.env"
fi
LAN_HTTP_IP="$(sed -n 's/^LAN_HTTP_IP=//p' "${SERVICE_DIR}/.env")"
[[ -n "${LAN_HTTP_IP}" && "${LAN_HTTP_IP}" != "0.0.0.0" ]] || exit 1
ip -4 addr show | grep -Fq "inet ${LAN_HTTP_IP}/" || { echo "Selected LAN IP is not assigned." >&2; exit 1; }
docker network inspect kids_ingress >/dev/null
# Validate the rendered proxy before interrupting Jellyfin's existing port-80 binding.
docker run --rm --network none -e "LAN_HTTP_IP=${LAN_HTTP_IP}" \
    -v "${SERVICE_DIR}/default.conf.template:/etc/nginx/templates/default.conf.template:ro" \
    nginx:1.29.1-alpine nginx -t
docker compose -f "${SERVICE_DIR}/compose.yml" config --quiet
if docker inspect jellyfin --format '{{json .HostConfig.PortBindings}}' | grep -q '"HostPort":"80"'; then
    # Recover only the current hardware values, never read or rewrite the protected .env.
    export JELLYFIN_LAN_IP="${LAN_HTTP_IP}"
    JELLYFIN_RENDER_DEVICE="$(docker inspect jellyfin --format '{{(index .HostConfig.Devices 0).PathOnHost}}')"
    JELLYFIN_RENDER_GID="$(docker inspect jellyfin --format '{{index .HostConfig.GroupAdd 0}}')"
    export JELLYFIN_RENDER_DEVICE JELLYFIN_RENDER_GID
    # The repository definition must publish only 8096, with port 80 owned by this proxy.
    if docker compose --env-file /dev/null -f "${REPO_DIR}/services/jellyfin/compose.yml" config --format json | grep -q '"published": "80"'; then
        echo "Remove Jellyfin's direct port-80 publication before migration." >&2
        exit 1
    fi
    docker compose --env-file /dev/null -f "${REPO_DIR}/services/jellyfin/compose.yml" up -d --wait --wait-timeout 180
fi
docker compose -f "${SERVICE_DIR}/compose.yml" up -d --wait --wait-timeout 90
curl --fail --silent --show-error --output /dev/null --resolve "kids.home.arpa:80:${LAN_HTTP_IP}" http://kids.home.arpa/
curl --fail --silent --show-error --output /dev/null --resolve "jellyfin.home.arpa:80:${LAN_HTTP_IP}" http://jellyfin.home.arpa/health
echo "LAN hostnames ready: http://kids.home.arpa/ and http://jellyfin.home.arpa/"
