#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
SERVICE_DIR="${REPO_DIR}/services/cloudflared"
RUNTIME_DIR="/srv/homelab/appdata/cloudflared"

usage() {
    echo "Usage: sudo $0 --mode safe|test|sso" >&2
    exit 2
}

[[ "${EUID}" -eq 0 ]] || { echo "ERROR: Run this script as root." >&2; exit 1; }
[[ "${1:-}" == "--mode" ]] || usage
MODE="${2:-}"
[[ "${MODE}" == "safe" || "${MODE}" == "test" || "${MODE}" == "sso" ]] || usage
[[ -z "${3:-}" ]] || usage

ENV_FILE="${SERVICE_DIR}/.env"
[[ -f "${ENV_FILE}" ]] || { echo "ERROR: Copy ${SERVICE_DIR}/.env.example to ${ENV_FILE} and set its values." >&2; exit 1; }

# This file is operator-controlled, local, and ignored by Git.
# shellcheck disable=SC1090
source "${ENV_FILE}"
: "${CLOUDFLARE_DOMAIN:?CLOUDFLARE_DOMAIN is required}"
: "${CLOUDFLARE_TUNNEL_ID:?CLOUDFLARE_TUNNEL_ID is required}"
: "${CLOUDFLARE_TUNNEL_CREDENTIALS_FILE:?CLOUDFLARE_TUNNEL_CREDENTIALS_FILE is required}"

[[ "${CLOUDFLARE_DOMAIN}" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "ERROR: CLOUDFLARE_DOMAIN is invalid." >&2; exit 1; }
[[ "${CLOUDFLARE_TUNNEL_ID}" =~ ^[A-Fa-f0-9-]+$ ]] || { echo "ERROR: CLOUDFLARE_TUNNEL_ID is invalid." >&2; exit 1; }
[[ -f "${CLOUDFLARE_TUNNEL_CREDENTIALS_FILE}" ]] || { echo "ERROR: Tunnel credential file not found." >&2; exit 1; }

TEMPLATE="${REPO_DIR}/config/cloudflared/config.${MODE}.yml.template"
mkdir -p "${RUNTIME_DIR}"
RUNTIME_CREDENTIAL_FILE="${RUNTIME_DIR}/${CLOUDFLARE_TUNNEL_ID}.json"
if [[ "${CLOUDFLARE_TUNNEL_CREDENTIALS_FILE}" != "${RUNTIME_CREDENTIAL_FILE}" ]]; then
    install -m 0600 "${CLOUDFLARE_TUNNEL_CREDENTIALS_FILE}" "${RUNTIME_CREDENTIAL_FILE}"
else
    chmod 0600 "${RUNTIME_CREDENTIAL_FILE}"
fi

sed \
    -e "s|__TUNNEL_ID__|${CLOUDFLARE_TUNNEL_ID}|g" \
    -e "s|__CREDENTIALS_FILE__|/etc/cloudflared/${CLOUDFLARE_TUNNEL_ID}.json|g" \
    -e "s|__DOMAIN__|${CLOUDFLARE_DOMAIN}|g" \
    "${TEMPLATE}" > "${RUNTIME_DIR}/config.yml"
chmod 0600 "${RUNTIME_DIR}/config.yml"

echo "Rendered ${MODE} tunnel configuration at ${RUNTIME_DIR}/config.yml."
if [[ "${MODE}" == "test" ]]; then
    echo "WARNING: TEST MODE is unauthenticated unless Cloudflare Access is already enforced."
elif [[ "${MODE}" == "sso" ]]; then
    echo "SSO mode active: Audiobookshelf uses native OIDC and Books uses the Authentik proxy."
else
    echo "SAFE MODE active: application hostnames return 404; Authentik remains routed."
fi
