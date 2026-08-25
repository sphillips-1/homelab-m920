#!/usr/bin/env bash
set -euo pipefail

HOMELAB_ROOT="/srv/homelab"
STORAGE_ROOT="${HOMELAB_ROOT}/storage"

APPDATA_ROOT="${HOMELAB_ROOT}/appdata"
CACHE_ROOT="${HOMELAB_ROOT}/cache"
MEDIA_ROOT="${HOMELAB_ROOT}/media"
AUDIOBOOK_ROOT="${MEDIA_ROOT}/audiobooks"
BOOKS_ROOT="${AUDIOBOOK_ROOT}/Books"
EBOOKS_ROOT="${MEDIA_ROOT}/ebooks"
BACKUP_ROOT="${HOMELAB_ROOT}/backups"

echo "==> Creating persistent Homelab directories"

mkdir -p \
    "${APPDATA_ROOT}/audiobookshelf" \
    "${APPDATA_ROOT}/audiobookshelf/metadata" \
    "${APPDATA_ROOT}/calibre-web" \
    "${APPDATA_ROOT}/cloudflared" \
    "${APPDATA_ROOT}/authentik/postgresql" \
    "${APPDATA_ROOT}/authentik/data" \
    "${APPDATA_ROOT}/authentik/certs" \
    "${APPDATA_ROOT}/authentik/custom-templates" \
    "${APPDATA_ROOT}/homepage" \
    "${APPDATA_ROOT}/monitoring" \
    "${APPDATA_ROOT}/monitoring/beszel-data" \
    "${APPDATA_ROOT}/monitoring/beszel-agent-data" \
    "${APPDATA_ROOT}/monitoring/beszel-socket" \
    "${APPDATA_ROOT}/jellyfin" \
    "${CACHE_ROOT}/jellyfin" \
    "${BOOKS_ROOT}" \
    "${EBOOKS_ROOT}" \
    "${MEDIA_ROOT}/movies" \
    "${MEDIA_ROOT}/tv" \
    "${MEDIA_ROOT}/.beszel" \
    "${STORAGE_ROOT}/.beszel" \
    "${BACKUP_ROOT}/appdata" \
    "${BACKUP_ROOT}/database" \
    "${BACKUP_ROOT}/authentik"

# Authentik uses UID/GID 1000 for application files. PostgreSQL manages its own
# data-directory ownership, so never recursively chown the parent on reruns.
chown -R 1000:1000 \
    "${APPDATA_ROOT}/authentik/data" \
    "${APPDATA_ROOT}/authentik/certs" \
    "${APPDATA_ROOT}/authentik/custom-templates"
chmod 700 "${BACKUP_ROOT}/authentik"

echo
echo "Persistent directory structure:"
echo

find "${HOMELAB_ROOT}" -maxdepth 3 -type d | sort

echo
echo "NOTE:"
echo " Audiobooks belong under:"
echo " ${BOOKS_ROOT}"
echo " Ebooks belong under:"
echo " ${EBOOKS_ROOT}"
echo " Movies belong under:"
echo " ${MEDIA_ROOT}/movies"
echo " TV shows belong under:"
echo " ${MEDIA_ROOT}/tv"
echo
echo " Compatibility links are created separately by:"
echo " /opt/homelab/scripts/create-audiobook-links.sh"
echo
echo "Directory creation complete."
