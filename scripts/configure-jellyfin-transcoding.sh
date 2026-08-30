#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="/srv/homelab/appdata/jellyfin/config/encoding.xml"
BACKUP_FILE="${CONFIG_FILE}.pre-qsv"

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
docker inspect jellyfin >/dev/null 2>&1 || fail "The jellyfin container does not exist."

for _ in {1..30}; do
    [[ -f "${CONFIG_FILE}" ]] && break
    sleep 1
done
[[ -f "${CONFIG_FILE}" ]] || fail "Jellyfin did not create ${CONFIG_FILE}."

current_type="$(sed -n 's:.*<HardwareAccelerationType>\([^<]*\)</HardwareAccelerationType>.*:\1:p' "${CONFIG_FILE}")"
[[ -n "${current_type}" ]] || fail "Could not read HardwareAccelerationType from ${CONFIG_FILE}."

if [[ "${current_type}" == "qsv" ]]; then
    echo "Jellyfin Intel Quick Sync transcoding is already configured."
    exit 0
fi

[[ "$(grep -c '<HardwareAccelerationType>' "${CONFIG_FILE}")" -eq 1 ]] || \
    fail "Expected exactly one HardwareAccelerationType element in ${CONFIG_FILE}."

was_running=false
temp_file=""
if [[ "$(docker inspect --format '{{.State.Running}}' jellyfin)" == "true" ]]; then
    was_running=true
    docker stop jellyfin >/dev/null
fi

cleanup() {
    [[ -z "${temp_file}" ]] || rm -f "${temp_file}"
    if [[ "${was_running}" == "true" ]]; then
        docker start jellyfin >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

cp --preserve=mode,ownership,timestamps --no-clobber "${CONFIG_FILE}" "${BACKUP_FILE}"
temp_file="$(mktemp "${CONFIG_FILE}.tmp.XXXXXX")"
sed 's:<HardwareAccelerationType>[^<]*</HardwareAccelerationType>:<HardwareAccelerationType>qsv</HardwareAccelerationType>:' \
    "${CONFIG_FILE}" > "${temp_file}"
chown --reference="${CONFIG_FILE}" "${temp_file}"
chmod --reference="${CONFIG_FILE}" "${temp_file}"
mv -f "${temp_file}" "${CONFIG_FILE}"

if [[ "${was_running}" == "true" ]]; then
    docker start jellyfin >/dev/null
fi
trap - EXIT

echo "Jellyfin hardware acceleration changed from ${current_type} to qsv."
