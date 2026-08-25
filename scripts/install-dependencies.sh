#!/usr/bin/env bash
set -euo pipefail

log() {
    echo
    echo "==> $1"
}

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

if [[ "${EUID}" -ne 0 ]]; then
    fail "Run this script as root."
fi

log "Installing common packages"

apt-get update

apt-get install -y \
    ca-certificates \
    curl \
    git \
    gnupg \
    intel-gpu-tools \
    iproute2 \
    jq \
    rsync \
    unzip \
    vim \
    wget \
    vainfo

log "Installing Docker"

install -m 0755 -d /etc/apt/keyrings

if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc

    chmod a+r /etc/apt/keyrings/docker.asc
fi

if [[ ! -f /etc/apt/sources.list.d/docker.list ]]; then
    cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable
EOF
fi

apt-get update

apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

systemctl enable --now docker

log "Installing Tailscale"

if ! command -v tailscale >/dev/null 2>&1; then
    curl -fsSL https://tailscale.com/install.sh | sh
fi

systemctl enable --now tailscaled

log "Dependency installation complete"

echo
echo "Installed:"
echo "  Git:      $(git --version)"
echo "  Docker:   $(docker --version)"
echo "  Compose:  $(docker compose version)"
echo "  Tailscale: $(tailscale version | head -n 1)"
