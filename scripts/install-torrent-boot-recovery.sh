#!/usr/bin/env bash
set -euo pipefail
[[ "${EUID}" -eq 0 ]] || { echo "Run as root." >&2; exit 1; }
cat > /etc/systemd/system/homelab-torrent-recovery.service <<'EOF'
[Unit]
Description=Restore torrent shared networking after Docker startup
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
PartOf=docker.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=/usr/bin/flock -w 600 /run/lock/homelab-deploy.lock /bin/bash /opt/homelab/scripts/recover-torrent-stack.sh
TimeoutStartSec=1000
Restart=on-failure
RestartSec=30

[Install]
WantedBy=docker.service
EOF
chmod 0644 /etc/systemd/system/homelab-torrent-recovery.service
systemctl daemon-reload
# Deployment runs recovery directly under its existing lock. Do not start the
# unit here: that would deadlock against the pipeline's deployment lock.
systemctl enable homelab-torrent-recovery.service
