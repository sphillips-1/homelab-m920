#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
RUNNER_USER="${1:-}"
COMMAND_PATH="/usr/local/sbin/homelab-deploy"
SUDOERS_PATH="/etc/sudoers.d/homelab-deploy"

[[ "${EUID}" -eq 0 ]] || { echo "ERROR: Run this script as root." >&2; exit 1; }
[[ "${RUNNER_USER}" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || {
    echo "Usage: sudo $0 RUNNER_USER" >&2
    exit 2
}
id "${RUNNER_USER}" >/dev/null 2>&1 || { echo "ERROR: User ${RUNNER_USER} does not exist." >&2; exit 1; }
command -v visudo >/dev/null 2>&1 || { echo "ERROR: visudo is required." >&2; exit 1; }

install -o root -g root -m 0755 "${REPO_DIR}/scripts/deploy-release.sh" "${COMMAND_PATH}"

sudoers_tmp="$(mktemp)"
trap 'rm -f "${sudoers_tmp}"' EXIT
printf '%s ALL=(root) NOPASSWD: %s *\n' "${RUNNER_USER}" "${COMMAND_PATH}" > "${sudoers_tmp}"
chmod 0440 "${sudoers_tmp}"
visudo --check --file="${sudoers_tmp}"
install -o root -g root -m 0440 "${sudoers_tmp}" "${SUDOERS_PATH}"

echo "Installed ${COMMAND_PATH} and restricted sudo policy for ${RUNNER_USER}."
echo "Add the labels linux, x64, and m920 to this GitHub Actions runner."
