#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with sudo from the repository checkout." >&2
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_file="${repo_root}/terraform/authentik/adoption.env"
target_file="${repo_root}/services/authentik/.env"
names=(
  AUTHENTIK_AUDIOBOOKSHELF_CLIENT_SECRET
  AUTHENTIK_GOOGLE_CLIENT_ID
  AUTHENTIK_GOOGLE_CLIENT_SECRET
  AUTHENTIK_GOOGLE_EMAIL_ALLOWLIST_EXPRESSION
)

for path in "${source_file}" "${target_file}"; do
  resolved="$(readlink -f -- "${path}")"
  case "${resolved}" in
    "${repo_root}"/*) ;;
    *) echo "Refusing path outside ${repo_root}: ${resolved}" >&2; exit 1 ;;
  esac
  [[ -f "${resolved}" ]] || { echo "Missing required file: ${resolved}" >&2; exit 1; }
done

for name in "${names[@]}"; do
  [[ $(grep -c "^${name}=" "${source_file}") -eq 1 ]] || {
    echo "Expected exactly one ${name} assignment in ${source_file}." >&2
    exit 1
  }
  if grep -q "^${name}=" "${target_file}"; then
    echo "Refusing to duplicate existing ${name} in ${target_file}." >&2
    exit 1
  fi
done

backup="${target_file}.pre-terraform-adoption"
[[ ! -e "${backup}" ]] || { echo "Refusing to overwrite backup: ${backup}" >&2; exit 1; }
install -m 0600 -o root -g root "${target_file}" "${backup}"

{
  printf '\n# Terraform-managed Authentik blueprint references\n'
  cat "${source_file}"
} >>"${target_file}"
chmod 0600 "${target_file}"

docker compose -f "${repo_root}/services/authentik/compose.yml" up -d server worker

for name in "${names[@]}"; do
  docker exec authentik-worker printenv "${name}" >/dev/null
  echo "${name}=PRESENT"
done

echo "Installed adoption variables. Backup: ${backup}"
echo "After copying them to the off-host secret store, securely remove ${source_file}."
