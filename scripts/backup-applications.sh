#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="/srv/homelab/backups"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/applications/${STAMP}"

[[ "${EUID}" -eq 0 ]] || { echo "ERROR: Run this script as root." >&2; exit 1; }
install -d -m 0700 "${DEST}"

restart_apps() {
    docker start audiobookshelf calibre-web >/dev/null 2>&1 || true
}
trap restart_apps EXIT

docker stop audiobookshelf calibre-web >/dev/null
tar -C /srv/homelab/appdata/audiobookshelf -czf "${DEST}/audiobookshelf-appdata.tar.gz" .
tar -C /srv/homelab/appdata/calibre-web -czf "${DEST}/calibre-web-appdata.tar.gz" .
tar -C /srv/homelab/media/ebooks -czf "${DEST}/calibre-library.tar.gz" .
chmod 0600 "${DEST}"/*
restart_apps
trap - EXIT

echo "Application backup created at ${DEST}."
echo "Copy it to encrypted off-host storage."
