#!/usr/bin/env bash
set -euo pipefail
[[ "${EUID}" -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
dest="/srv/homelab/backups/readest/$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 "${dest}"
restart_readest() { docker start readest-auth readest-rest readest-client readest-sso readest-storage >/dev/null; }
trap restart_readest EXIT
docker stop readest-auth readest-rest readest-client readest-sso readest-storage >/dev/null
docker exec readest-db pg_dump -U supabase_admin -d postgres -Fc > "${dest}/postgres.dump"
tar -C /srv/homelab/appdata/readest -czf "${dest}/storage-config.tar.gz" minio postgres-config
install -m 0600 /opt/homelab/services/readest/.env "${dest}/readest.env"
chmod 0600 "${dest}"/*
restart_readest
trap - EXIT
echo "Readest backup created at ${dest}. Copy to encrypted off-host storage."
