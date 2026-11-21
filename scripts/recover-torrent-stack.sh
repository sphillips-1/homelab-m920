#!/usr/bin/env bash
set -euo pipefail

repo=/opt/homelab
compose=(docker compose -f "${repo}/services/qbittorrent-m920/compose.yml")
if [[ -d /srv/homelab/video-data/media/.jellyfin-imports ]] &&
   bash "${repo}/scripts/check-m920-video-storage.sh"; then
    compose+=(-f "${repo}/services/qbittorrent-m920/compose.video.yml")
fi
bash "${repo}/scripts/check-m920-torrent-storage.sh"
"${compose[@]}" up -d --wait --wait-timeout 180 qbittorrent
# Recreate namespace-sharing services after the app's network is ready. Docker's
# automatic restart at boot does not enforce Compose dependency ordering.
"${compose[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 gateway audiobook-importer
bash "${repo}/scripts/verify-torrent-connectivity.sh"
