#!/usr/bin/env bash
set -euo pipefail

HOMELAB_ROOT="/srv/homelab"

APPDATA_ROOT="${HOMELAB_ROOT}/appdata"
MEDIA_ROOT="${HOMELAB_ROOT}/media"
AUDIOBOOK_ROOT="${MEDIA_ROOT}/audiobooks"
BOOKS_ROOT="${AUDIOBOOK_ROOT}/Books"
BACKUP_ROOT="${HOMELAB_ROOT}/backups"

echo "==> Creating persistent Homelab directories"

mkdir -p
"${APPDATA_ROOT}/audiobookshelf"
"${APPDATA_ROOT}/audiobookshelf/metadata"
"${APPDATA_ROOT}/calibre-web"
"${APPDATA_ROOT}/homepage"
"${APPDATA_ROOT}/monitoring"

mkdir -p
"${AUDIOBOOK_ROOT}"
"${BOOKS_ROOT}"
"${AUDIOBOOK_ROOT}/ebooks"

mkdir -p
"${BACKUP_ROOT}/appdata"
"${BACKUP_ROOT}/database"

echo
echo "Persistent directory structure:"
echo

find "${HOMELAB_ROOT}"
-maxdepth 3
-type d
| sort

echo
echo "NOTE:"
echo " Audiobooks belong under:"
echo " ${BOOKS_ROOT}"
echo
echo " Compatibility links are created separately by:"
echo " /opt/homelab/scripts/create-audiobook-links.sh"
echo
echo "Directory creation complete."