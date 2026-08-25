#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
ENV_FILE="${REPO_DIR}/services/jellyfin/.env"
LAN_IP_OVERRIDE="${JELLYFIN_LAN_IP:-}"

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ -d /dev/dri ]] || fail "/dev/dri is missing. Enable the Intel iGPU in firmware and load the i915 driver."

echo "==> Detecting Intel render device"
ls -l /dev/dri

mapfile -t render_devices < <(find /dev/dri -maxdepth 1 -type c -name 'renderD*' -print | sort)
(( ${#render_devices[@]} > 0 )) || fail "No /dev/dri/renderD* device was found."

render_device="${render_devices[0]}"
render_gid="$(stat -c '%g' "${render_device}")"
[[ "${render_gid}" =~ ^[0-9]+$ ]] || fail "Could not determine the group ID for ${render_device}."

existing_lan_ip=""
if [[ -f "${ENV_FILE}" ]]; then
    existing_lan_ip="$(sed -n 's/^JELLYFIN_LAN_IP=//p' "${ENV_FILE}")"
fi

if [[ -n "${LAN_IP_OVERRIDE}" ]]; then
    lan_ip="${LAN_IP_OVERRIDE}"
elif [[ -n "${existing_lan_ip}" ]] &&
     ip -4 -o addr show | awk '{ split($4, address, "/"); print address[1] }' | grep -Fxq "${existing_lan_ip}"; then
    lan_ip="${existing_lan_ip}"
else
    default_interface="$(ip -4 route show default | awk 'NR == 1 { print $5 }')"
    [[ -n "${default_interface}" ]] || fail "No IPv4 default-route interface was found. Set JELLYFIN_LAN_IP explicitly."
    lan_ip="$(ip -4 -o addr show dev "${default_interface}" scope global | awk 'NR == 1 { split($4, address, "/"); print address[1] }')"
fi

[[ "${lan_ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail "Invalid LAN IPv4 address: ${lan_ip:-empty}"
ip -4 -o addr show | awk '{ split($4, address, "/"); print address[1] }' | grep -Fxq "${lan_ip}" || \
    fail "${lan_ip} is not assigned to this host."

umask 077
temp_file="$(mktemp "${ENV_FILE}.tmp.XXXXXX")"
cleanup() {
    rm -f "${temp_file}"
}
trap cleanup EXIT

printf 'JELLYFIN_LAN_IP=%s\nJELLYFIN_RENDER_DEVICE=%s\nJELLYFIN_RENDER_GID=%s\n' \
    "${lan_ip}" "${render_device}" "${render_gid}" > "${temp_file}"
chown root:root "${temp_file}"
chmod 0600 "${temp_file}"
mv -f "${temp_file}" "${ENV_FILE}"
trap - EXIT

echo "Jellyfin host configuration written to ${ENV_FILE}:"
echo "  LAN endpoint:  http://${lan_ip}:8096"
echo "  Render device: ${render_device} (supplemental GID ${render_gid})"
