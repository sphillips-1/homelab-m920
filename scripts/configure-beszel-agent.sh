#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
SERVICE_DIR="${REPO_DIR}/services/monitoring"
ENV_FILE="${SERVICE_DIR}/.env"

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ -f "${SERVICE_DIR}/compose.yml" ]] || fail "Monitoring Compose file not found."
[[ -t 0 ]] || fail "Run this script from an interactive terminal."

echo "Configure or rotate the local Beszel agent credentials."
echo "Paste the values from Beszel's Add system dialog."
echo

read -r -p "Public key: " BESZEL_KEY
read -r -s -p "Token: " BESZEL_TOKEN
echo

[[ "${BESZEL_KEY}" == ssh-*\ * ]] || fail "The public key must begin with an SSH key type and include key data."
[[ -n "${BESZEL_TOKEN}" ]] || fail "Token cannot be empty."
[[ "${BESZEL_KEY}" != *$'\n'* && "${BESZEL_KEY}" != *$'\r'* ]] || fail "Public key must be one line."
[[ "${BESZEL_TOKEN}" != *$'\n'* && "${BESZEL_TOKEN}" != *$'\r'* ]] || fail "Token must be one line."
[[ "${BESZEL_KEY}" != *'"'* && "${BESZEL_KEY}" != *'\\'* ]] || fail "Public key contains unsupported quoting characters."
[[ "${BESZEL_TOKEN}" != *'"'* && "${BESZEL_TOKEN}" != *'\\'* ]] || fail "Token contains unsupported quoting characters."

umask 077
TEMP_FILE="$(mktemp "${SERVICE_DIR}/.env.tmp.XXXXXX")"
cleanup() {
    rm -f "${TEMP_FILE}"
}
trap cleanup EXIT

printf 'KEY="%s"\nTOKEN="%s"\n' "${BESZEL_KEY}" "${BESZEL_TOKEN}" > "${TEMP_FILE}"
chown root:root "${TEMP_FILE}"
chmod 0600 "${TEMP_FILE}"
mv -f "${TEMP_FILE}" "${ENV_FILE}"
trap - EXIT

echo "Credentials installed at ${ENV_FILE}."
echo "Recreating the Beszel agent..."

cd "${SERVICE_DIR}"
docker compose --profile agent up -d --force-recreate beszel-agent

echo
docker compose --profile agent ps beszel-agent
echo
echo "Beszel agent credentials updated."
