#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
ENV_FILE="${REPO_DIR}/services/cloudflared/.env"
MODE="${1:-safe}"

[[ "${MODE}" == "safe" || "${MODE}" == "test" ]] || {
    echo "Usage: $0 [safe|test]" >&2
    exit 2
}
[[ -f "${ENV_FILE}" ]] || { echo "ERROR: ${ENV_FILE} is missing." >&2; exit 1; }
# shellcheck disable=SC1090
source "${ENV_FILE}"
: "${CLOUDFLARE_DOMAIN:?CLOUDFLARE_DOMAIN is required}"

echo "==> Compose validation"
docker compose -f "${REPO_DIR}/services/audiobookshelf/compose.yml" config -q
docker compose -f "${REPO_DIR}/services/calibre-web/compose.yml" config -q
docker compose -f "${REPO_DIR}/services/cloudflared/compose.yml" config -q

if ! docker inspect --format '{{.State.Running}}' cloudflared 2>/dev/null | grep -qx true; then
    echo "ERROR: The cloudflared container is not running." >&2
    echo "Deploy it with: sudo docker compose -f ${REPO_DIR}/services/cloudflared/compose.yml up -d" >&2
    echo "Then inspect: docker logs --tail 100 cloudflared" >&2
    exit 1
fi

docker exec cloudflared cloudflared tunnel --config /etc/cloudflared/config.yml ingress validate

echo "==> Expected container status"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' \
  --filter name='^(audiobookshelf|calibre-web|cloudflared)$'

echo "==> Host publication check (must be loopback only)"
for port in 13378 8083; do
    if ss -ltnH "( sport = :${port} )" | awk '{print $4}' | grep -Eq '(^|\[::\]:|0\.0\.0\.0:)'; then
        echo "ERROR: Port ${port} is published beyond loopback." >&2
        exit 1
    fi
done

echo "==> Local tunnel-to-container connectivity"
docker run --rm --network homelab curlimages/curl:latest -fsS -o /dev/null http://audiobookshelf:80
docker run --rm --network homelab curlimages/curl:latest -fsS -o /dev/null http://calibre-web:8083

echo "==> Tunnel connection log"
docker logs --tail 100 cloudflared | grep -Ei 'registered tunnel connection|connection.*registered|connected' || {
    echo "ERROR: No successful tunnel connection was found in the recent cloudflared log." >&2
    exit 1
}

for hostname in "audiobooks.${CLOUDFLARE_DOMAIN}" "books.${CLOUDFLARE_DOMAIN}"; do
    echo "==> DNS and HTTPS: ${hostname}"
    getent ahosts "${hostname}" >/dev/null || { echo "ERROR: DNS does not resolve: ${hostname}" >&2; exit 1; }
    if [[ "${MODE}" == "safe" ]]; then
        headers="$(curl --silent --show-error --dump-header - --output /dev/null "https://${hostname}")"
        status="$(awk 'toupper($1) ~ /^HTTP\// { code=$2 } END { print code }' <<<"${headers}")"
        if [[ "${status}" == "404" ]]; then
            continue
        fi
        if [[ "${status}" == "302" ]] && grep -Eqi '^location: .*([.]cloudflareaccess[.]com|/cdn-cgi/access/)' <<<"${headers}"; then
            echo "Cloudflare Access redirect confirmed for ${hostname}."
            continue
        fi
        echo "ERROR: Expected a 404 or Cloudflare Access redirect for ${hostname}; got HTTP ${status:-unknown}." >&2
        exit 1
    else
        curl --fail --silent --show-error --output /dev/null "https://${hostname}"
    fi
done

echo "Verification passed. No router port forwarding is required by Cloudflare Tunnel."
