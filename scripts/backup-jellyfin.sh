#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="/srv/homelab/backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/applications/${STAMP}"

[[ "${EUID}" -eq 0 ]] || { echo "ERROR: Run this script as root." >&2; exit 1; }
install -d -m 0700 "${DEST}"

restart_jellyfin() {
    docker start jellyfin >/dev/null 2>&1 || true
}
trap restart_jellyfin EXIT

docker stop jellyfin >/dev/null
tar -C /srv/homelab/appdata/jellyfin -czf "${DEST}/jellyfin-appdata.tar.gz" .
chmod 0600 "${DEST}/jellyfin-appdata.tar.gz"
restart_jellyfin
trap - EXIT

echo "Jellyfin application backup created at ${DEST}."
echo "Media and transcode cache are intentionally excluded."
