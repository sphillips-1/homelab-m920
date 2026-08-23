#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
SERVICE_DIR="${REPO_DIR}/services/cloudflared"
RUNTIME_DIR="/srv/homelab/appdata/cloudflared"
ENV_FILE="${SERVICE_DIR}/.env"
TUNNEL_NAME="homelab-m920-local"
DOMAIN=""
TUNNEL_ID=""
VERIFY=false

usage() {
    cat <<'EOF'
Usage: sudo bash scripts/setup-cloudflared-tunnel.sh --domain example.com [options]

Creates or reuses a locally managed Cloudflare Tunnel, writes the ignored local
environment file, renders PRE-SSO SAFE mode, and deploys the connector.

Options:
  --domain DOMAIN       Cloudflare zone, without a protocol or subdomain.
  --tunnel-name NAME    Tunnel name when a new tunnel is needed (default:
                        homelab-m920-local).
  --tunnel-id UUID      Reuse this existing local <UUID>.json credential.
  --verify              Run full DNS/HTTPS verification after deployment.
  -h, --help            Show this help.
EOF
}

fail() { echo "ERROR: $1" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) DOMAIN="${2:-}"; shift 2 ;;
        --tunnel-name) TUNNEL_NAME="${2:-}"; shift 2 ;;
        --tunnel-id) TUNNEL_ID="${2:-}"; shift 2 ;;
        --verify) VERIFY=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage; fail "Unknown option: $1" ;;
    esac
done

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ -d "${REPO_DIR}" ]] || fail "Repository not found at ${REPO_DIR}."
command -v docker >/dev/null 2>&1 || fail "Docker is not installed."
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is not installed."

if [[ -f "${ENV_FILE}" ]]; then
    # This local, ignored file is created by this script.
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    DOMAIN="${DOMAIN:-${CLOUDFLARE_DOMAIN:-}}"
    TUNNEL_ID="${TUNNEL_ID:-${CLOUDFLARE_TUNNEL_ID:-}}"
fi

[[ -n "${DOMAIN}" ]] || fail "Pass --domain (for example: --domain example.com)."
[[ "${DOMAIN}" =~ ^[A-Za-z0-9.-]+$ ]] || fail "Domain is invalid."

"${REPO_DIR}/scripts/create-directories.sh" >/dev/null
chmod 700 "${RUNTIME_DIR}"

CREDENTIAL_FILE=""
if [[ -n "${TUNNEL_ID}" ]]; then
    CREDENTIAL_FILE="${RUNTIME_DIR}/${TUNNEL_ID}.json"
    if [[ ! -f "${CREDENTIAL_FILE}" ]]; then
        echo "Configured tunnel credential is absent; checking local credentials."
        TUNNEL_ID=""
        CREDENTIAL_FILE=""
    fi
fi

if [[ -z "${TUNNEL_ID}" ]]; then
    mapfile -t credentials < <(find "${RUNTIME_DIR}" -maxdepth 1 -type f -name '*.json' -printf '%f\n' | sort)
    if [[ ${#credentials[@]} -eq 1 ]]; then
        TUNNEL_ID="${credentials[0]%.json}"
        CREDENTIAL_FILE="${RUNTIME_DIR}/${credentials[0]}"
        echo "Reusing local tunnel credential: ${TUNNEL_ID}"
    elif [[ ${#credentials[@]} -gt 1 ]]; then
        fail "Multiple local tunnel credentials found. Re-run with --tunnel-id <UUID>."
    else
        echo "No local tunnel credential found. Cloudflare login is required."
        docker run --rm -it --user 0:0 \
            -v "${RUNTIME_DIR}:/root/.cloudflared" \
            cloudflare/cloudflared:latest tunnel login
        docker run --rm -it --user 0:0 \
            -v "${RUNTIME_DIR}:/root/.cloudflared" \
            cloudflare/cloudflared:latest tunnel create "${TUNNEL_NAME}"
        mapfile -t credentials < <(find "${RUNTIME_DIR}" -maxdepth 1 -type f -name '*.json' -printf '%f\n' | sort)
        [[ ${#credentials[@]} -eq 1 ]] || fail "Expected exactly one JSON credential after tunnel creation."
        TUNNEL_ID="${credentials[0]%.json}"
        CREDENTIAL_FILE="${RUNTIME_DIR}/${credentials[0]}"
    fi
fi

[[ "${TUNNEL_ID}" =~ ^[A-Fa-f0-9-]+$ ]] || fail "Tunnel ID is invalid."
install -o root -g root -m 0600 /dev/null "${ENV_FILE}"
printf 'CLOUDFLARE_DOMAIN=%s\nCLOUDFLARE_TUNNEL_ID=%s\nCLOUDFLARE_TUNNEL_CREDENTIALS_FILE=%s\n' \
    "${DOMAIN}" "${TUNNEL_ID}" "${CREDENTIAL_FILE}" > "${ENV_FILE}"
chmod 0600 "${CREDENTIAL_FILE}"

echo "Rendering PRE-SSO SAFE mode."
bash "${REPO_DIR}/scripts/configure-cloudflared.sh" --mode safe

echo "Deploying cloudflared."
docker compose -f "${SERVICE_DIR}/compose.yml" up -d --force-recreate

if [[ -f "${RUNTIME_DIR}/cert.pem" ]]; then
    rm -f "${RUNTIME_DIR}/cert.pem"
    echo "Removed temporary cert.pem; the tunnel JSON credential remains in use."
fi

echo
echo "Tunnel UUID: ${TUNNEL_ID}"
echo "Create proxied DNS CNAME records for audiobooks, books, status, and auth to:"
echo "${TUNNEL_ID}.cfargotunnel.com"
echo "SAFE mode is active: application hostnames return 404 until test mode is explicitly enabled."

if [[ "${VERIFY}" == true ]]; then
    bash "${REPO_DIR}/scripts/verify-cloudflare-tunnel.sh" safe
else
    echo "After DNS is configured, verify with:"
    echo "sudo bash ${REPO_DIR}/scripts/verify-cloudflare-tunnel.sh safe"
fi
