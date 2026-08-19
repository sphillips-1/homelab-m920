#!/usr/bin/env bash
set -euo pipefail

repo_dir="/opt/homelab"
label="${1:-shared}"
hours="${2:-24}"

if [[ ! "${label}" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]]; then
  echo "Usage: $0 [label] [valid-hours]" >&2
  exit 2
fi
if [[ ! "${hours}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: valid-hours must be a positive integer." >&2
  exit 2
fi

docker exec \
  -e "SERVICE_INVITE_LABEL=${label}" \
  -e "SERVICE_INVITE_HOURS=${hours}" \
  -i authentik-worker ak shell \
  < "${repo_dir}/scripts/create-service-invitation.py"
