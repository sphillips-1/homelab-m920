#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/sphillips-1/homelab-m920.git"
REPO_DIR="/opt/homelab"
BRANCH="main"

log() {
    echo
    echo "==> $1"
}

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
    fail "Run this script as root: sudo bash bootstrap.sh"
fi

if [[ ! -f /etc/os-release ]]; then
    fail "Unable to determine operating system."
fi

source /etc/os-release

if [[ "${ID}" != "debian" ]]; then
    fail "This bootstrap script is currently designed for Debian."
fi

log "Updating package lists"
apt-get update

log "Installing bootstrap dependencies"
apt-get install -y \
    ca-certificates \
    curl \
    git \
    gnupg \
    sudo

if [[ -d "${REPO_DIR}/.git" ]]; then
    log "Repository already exists at ${REPO_DIR}"

    git -C "${REPO_DIR}" fetch origin
    git -C "${REPO_DIR}" checkout "${BRANCH}"
    git -C "${REPO_DIR}" pull --ff-only origin "${BRANCH}"
else
    if [[ -e "${REPO_DIR}" ]]; then
        fail "${REPO_DIR} exists but is not a Git repository."
    fi

    log "Cloning Homelab repository"
    mkdir -p "$(dirname "${REPO_DIR}")"

    git clone \
        --branch "${BRANCH}" \
        "${REPO_URL}" \
        "${REPO_DIR}"
fi

log "Installing Homelab dependencies"

if [[ ! -x "${REPO_DIR}/scripts/install-dependencies.sh" ]]; then
    fail "Missing executable: ${REPO_DIR}/scripts/install-dependencies.sh"
fi

"${REPO_DIR}/scripts/install-dependencies.sh"

log "Bootstrap complete"

echo
echo "Homelab repository: ${REPO_DIR}"
echo
echo "Next steps:"
echo "  cd ${REPO_DIR}"
echo "  ./scripts/create-directories.sh"
echo "  ./scripts/deploy-services.sh"
echo "  sudo bash ./scripts/setup-cloudflared-tunnel.sh --domain example.com"
