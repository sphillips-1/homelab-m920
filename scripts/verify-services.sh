#!/usr/bin/env bash
set -euo pipefail

TIMEOUT_SECONDS="${VERIFY_TIMEOUT_SECONDS:-180}"
POLL_SECONDS=5

[[ "${EUID}" -eq 0 ]] || { echo "ERROR: Run this script as root." >&2; exit 1; }

wait_for_container() {
    local container="$1"
    local deadline=$((SECONDS + TIMEOUT_SECONDS))
    local status health

    while (( SECONDS < deadline )); do
        status="$(docker inspect --format '{{.State.Status}}' "${container}" 2>/dev/null || true)"
        health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${container}" 2>/dev/null || true)"

        if [[ "${status}" == "running" && ( "${health}" == "healthy" || "${health}" == "none" ) ]]; then
            echo "${container}: running (${health})"
            return 0
        fi
        if [[ "${status}" == "exited" || "${status}" == "dead" || "${health}" == "unhealthy" ]]; then
            docker logs --tail 100 "${container}" >&2 || true
            echo "ERROR: ${container} entered ${status:-unknown}/${health:-unknown}." >&2
            return 1
        fi
        sleep "${POLL_SECONDS}"
    done

    docker logs --tail 100 "${container}" >&2 || true
    echo "ERROR: Timed out waiting for ${container}." >&2
    return 1
}

for container in \
    authentik-postgresql \
    authentik-server \
    authentik-worker \
    authentik-invitation-provisioner \
    audiobookshelf \
    calibre-web \
    jellyfin \
    beszel; do
    wait_for_container "${container}"
done

if [[ -f /opt/homelab/services/monitoring/.env ]]; then
    wait_for_container beszel-agent
fi

if [[ -f /srv/homelab/appdata/cloudflared/config.yml ]]; then
    wait_for_container cloudflared
    docker exec cloudflared cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate
fi

echo "==> Verifying local application endpoints"
curl --fail --silent --show-error --output /dev/null --retry 12 --retry-delay 5 --retry-connrefused http://127.0.0.1:13378/
curl --fail --silent --show-error --output /dev/null --retry 12 --retry-delay 5 --retry-connrefused http://127.0.0.1:8083/
JELLYFIN_LAN_IP="$(sed -n 's/^JELLYFIN_LAN_IP=//p' /opt/homelab/services/jellyfin/.env)"
[[ -n "${JELLYFIN_LAN_IP}" ]] || { echo "ERROR: Jellyfin LAN address is not configured." >&2; exit 1; }
curl --fail --silent --show-error --output /dev/null --retry 12 --retry-delay 5 --retry-connrefused "http://${JELLYFIN_LAN_IP}:8096/health"
curl --fail --silent --show-error --output /dev/null --retry 12 --retry-delay 5 --retry-connrefused http://127.0.0.1:9000/-/health/ready/
curl --fail --silent --show-error --output /dev/null --retry 12 --retry-delay 5 --retry-connrefused http://127.0.0.1:8090/

echo "Service verification passed."
