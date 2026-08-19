#!/usr/bin/env bash
set -euo pipefail

repo_dir="/opt/homelab"
service_dir="${repo_dir}/services/authentik"
target="${service_dir}/.env.invitation"

if [[ "$(realpath "${service_dir}")" != "/opt/homelab/services/authentik" ]]; then
  echo "ERROR: unexpected Authentik service path." >&2
  exit 1
fi

if [[ -e "${target}" ]]; then
  grep -q '^AUDIOBOOKSHELF_API_TOKEN=.' "${target}"
  grep -q '^AUTHENTIK_INVITATION_PROVISIONER_TOKEN=.' "${target}"
  echo "Invitation environment already exists and contains both required keys."
  exit 0
fi

docker inspect audiobookshelf >/dev/null

abs_token="$(docker exec audiobookshelf node -e '
const sqlite3 = require("/app/node_modules/sqlite3")
const db = new sqlite3.Database("/config/absdatabase.sqlite")
db.get("SELECT token FROM users WHERE type = ? LIMIT 1", ["root"], (error, row) => {
  if (error) throw error
  if (!row || !row.token) throw new Error("Audiobookshelf root token not found")
  process.stdout.write(row.token)
  db.close()
})
')"
[[ -n "${abs_token}" ]] || { echo "ERROR: Audiobookshelf root token is empty." >&2; exit 1; }

provisioner_token="$(openssl rand -hex 32)"
temp_file="$(mktemp "${service_dir}/.env.invitation.tmp.XXXXXX")"
trap 'rm -f "${temp_file}"' EXIT
chmod 0600 "${temp_file}"
printf 'AUDIOBOOKSHELF_API_TOKEN=%s\n' "${abs_token}" > "${temp_file}"
printf 'AUTHENTIK_INVITATION_PROVISIONER_TOKEN=%s\n' "${provisioner_token}" >> "${temp_file}"
mv "${temp_file}" "${target}"
trap - EXIT

unset abs_token provisioner_token
echo "Installed protected invitation environment: ${target}"
