#!/usr/bin/env bash
set -euo pipefail

[[ "${EUID}" -eq 0 ]] || { echo "Run this script as root." >&2; exit 1; }
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash -n "${script_dir}/wait-for-jellyfin-address.sh"
install -o root -g root -m 0755 "${script_dir}/wait-for-jellyfin-address.sh" /usr/local/sbin/homelab-wait-for-jellyfin-address
install -d -o root -g root -m 0755 /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/homelab-network.conf <<'EOF'
[Service]
ExecStartPre=/usr/local/sbin/homelab-wait-for-jellyfin-address
EOF
chmod 0644 /etc/systemd/system/docker.service.d/homelab-network.conf
systemctl daemon-reload
echo "Installed Docker LAN-address guard. Docker was not restarted."
echo "The guard applies on the next Docker start, including the next boot."
