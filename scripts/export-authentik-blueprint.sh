#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="${1:-${repo_root}/terraform/authentik/raw-export.yaml}"

if [[ -e "${output}" ]]; then
  echo "Refusing to overwrite ${output}. Move or remove it after review." >&2
  exit 1
fi

umask 077
docker compose -f "${repo_root}/services/authentik/compose.yml" \
  exec -T worker ak export_blueprint >"${output}"

echo "Wrote private Authentik export to ${output}"
echo "Do not commit it. Remove users, tokens, events, sessions, invitations, and machine-specific objects."
echo "Replace every write-only secret with an Authentik !Env reference before saving the reviewed file as:"
echo "  ${repo_root}/terraform/authentik/homelab.yaml"
