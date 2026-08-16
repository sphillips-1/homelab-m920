#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
SERVICE_DIR="${REPO_DIR}/services/authentik"
BACKUP_ROOT="/srv/homelab/backups/authentik"
APPDATA_ROOT="/srv/homelab/appdata/authentik"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/${STAMP}"

[[ "${EUID}" -eq 0 ]] || { echo "ERROR: Run this script as root." >&2; exit 1; }
[[ -f "${SERVICE_DIR}/.env" ]] || { echo "ERROR: ${SERVICE_DIR}/.env is missing." >&2; exit 1; }
# shellcheck disable=SC1091
source "${SERVICE_DIR}/.env"
: "${PG_USER:=authentik}"
: "${PG_DB:=authentik}"
docker inspect authentik-postgresql >/dev/null 2>&1 || { echo "ERROR: Authentik PostgreSQL is not deployed." >&2; exit 1; }

install -d -m 0700 "${DEST}"

echo "==> Creating logical PostgreSQL backup"
docker compose -f "${SERVICE_DIR}/compose.yml" exec -T postgresql \
  pg_dump -U "${PG_USER}" -d "${PG_DB}" --clean --if-exists --create \
  > "${DEST}/authentik.sql"
chmod 0600 "${DEST}/authentik.sql"

echo "==> Archiving Authentik file data"
tar --create --gzip --file "${DEST}/authentik-files.tar.gz" \
  --directory "${APPDATA_ROOT}" data certs custom-templates
chmod 0600 "${DEST}/authentik-files.tar.gz"

echo "Backup created at ${DEST}."
echo "Back up services/authentik/.env separately in an encrypted secret store."
echo "Copy this backup off-host; a same-disk backup is not sufficient disaster recovery."
