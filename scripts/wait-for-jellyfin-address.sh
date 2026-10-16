#!/usr/bin/env bash
set -euo pipefail

# Read only the address; never source a Compose dotenv file as shell code.
env_file=/opt/homelab/services/jellyfin/.env
[[ -f "${env_file}" ]] || exit 0
address="$(sed -n 's/^JELLYFIN_LAN_IP=//p' "${env_file}")"
[[ "${address}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || {
    echo "Invalid or missing JELLYFIN_LAN_IP in ${env_file}" >&2
    exit 1
}

echo "Waiting for Jellyfin LAN address ${address} before Docker startup"
deadline=$((SECONDS + 120))
while (( SECONDS < deadline )); do
    if ip -4 -o addr show | awk '{ split($4, a, "/"); print a[1] }' | grep -Fxq "${address}"; then
        echo "Jellyfin LAN address is ready"
        exit 0
    fi
    sleep 1
done
echo "Jellyfin LAN address ${address} did not appear within 120 seconds" >&2
exit 1
