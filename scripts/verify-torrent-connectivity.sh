#!/usr/bin/env bash
set -euo pipefail

# Execute from the app namespace so a healthy but detached sidecar fails here.
docker exec m920-qbittorrent getent hosts www.debian.org >/dev/null
docker exec m920-qbittorrent curl --fail --silent --show-error --max-time 15 \
    https://www.debian.org/ --output /dev/null
docker exec m920-qbittorrent curl --fail --silent --show-error --max-time 5 \
    http://127.0.0.1:8080/api/v2/app/version --output /dev/null
docker exec m920-qbittorrent curl --fail --silent --show-error --max-time 5 \
    http://127.0.0.1:8092/health --output /dev/null
code="$(docker exec m920-qbittorrent curl --silent --show-error --max-time 10 \
    --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8091/)"
[[ "${code}" == 302 ]] || { echo "Torrent SSO gateway returned ${code}, expected 302" >&2; exit 1; }
echo "Torrent DNS, outbound HTTPS, API, importer, and SSO gateway passed."
