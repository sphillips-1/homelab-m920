#!/usr/bin/env bash
set -Eeuo pipefail

MEDIA_UUID="4c746df8-53bf-4717-a4ce-40b3b7e90ed2"
MEDIA_DEVICE="/dev/disk/by-uuid/${MEDIA_UUID}"
STORAGE_ROOT="/srv/homelab/storage"
MEDIA_ROOT="/srv/homelab/media"
OLD_MOUNT="${MEDIA_ROOT}/audiobooks"
FSTAB="/etc/fstab"
BACKUP="${FSTAB}.pre-homelab-media-migration"
TEMP_MOUNT=""
SERVICES_STOPPED=false

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

log() {
    echo
    echo "==> $1"
}

restart_services() {
    if [[ "${SERVICES_STOPPED}" == true ]]; then
        docker start audiobookshelf jellyfin >/dev/null 2>&1 || true
    fi
}

cleanup() {
    local exit_code=$?
    trap - EXIT
    if [[ -n "${TEMP_MOUNT}" ]] && mountpoint -q "${TEMP_MOUNT}"; then
        umount "${TEMP_MOUNT}" || true
    fi
    if [[ -n "${TEMP_MOUNT}" ]]; then
        rmdir "${TEMP_MOUNT}" 2>/dev/null || true
    fi
    restart_services
    exit "${exit_code}"
}
trap cleanup EXIT

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ -b "${MEDIA_DEVICE}" ]] || fail "Expected media filesystem ${MEDIA_DEVICE} was not found."
[[ "$(blkid -s TYPE -o value "${MEDIA_DEVICE}")" == "ext4" ]] || fail "The media filesystem is not ext4."

if [[ "$(findmnt -rn -M "${STORAGE_ROOT}" -o UUID 2>/dev/null || true)" == "${MEDIA_UUID}" ]] &&
   mountpoint -q "${MEDIA_ROOT}/movies" && mountpoint -q "${MEDIA_ROOT}/tv"; then
    echo "External media storage is already migrated."
    for directory in "${STORAGE_ROOT}" "${MEDIA_ROOT}/audiobooks" "${MEDIA_ROOT}/movies" "${MEDIA_ROOT}/tv"; do
        findmnt -M "${directory}"
    done
    exit 0
fi

for directory in "${MEDIA_ROOT}/movies" "${MEDIA_ROOT}/tv"; do
    [[ -d "${directory}" ]] || fail "Missing directory: ${directory}"
    [[ -z "$(find "${directory}" -mindepth 1 -maxdepth 1 -print -quit)" ]] || \
        fail "${directory} is not empty; refusing to hide or move existing data."
done

[[ "$(findmnt -rn -M "${OLD_MOUNT}" -o UUID 2>/dev/null || true)" == "${MEDIA_UUID}" ]] || \
    fail "Expected ${MEDIA_DEVICE} to be mounted at ${OLD_MOUNT}."

log "Stopping media consumers"
docker stop audiobookshelf jellyfin >/dev/null
SERVICES_STOPPED=true

log "Creating an alternate view of the external filesystem"
TEMP_MOUNT="$(mktemp -d /run/homelab-media-migration.XXXXXX)"
mount "${MEDIA_DEVICE}" "${TEMP_MOUNT}"

owner_uid="$(stat -c '%u' "${TEMP_MOUNT}")"
owner_gid="$(stat -c '%g' "${TEMP_MOUNT}")"

if [[ -d "${TEMP_MOUNT}/audiobooks/Books" ]]; then
    log "External filesystem already has the new directory layout; resuming mount configuration"
elif [[ -e "${TEMP_MOUNT}/audiobooks" ]]; then
    fail "An unexpected audiobooks entry exists without the expected Books directory."
else
    mkdir "${TEMP_MOUNT}/audiobooks"
    chown "${owner_uid}:${owner_gid}" "${TEMP_MOUNT}/audiobooks"

    log "Moving the legacy audiobook tree into the new audiobook directory"
    while IFS= read -r -d '' entry; do
        name="$(basename "${entry}")"
        [[ "${name}" == "lost+found" || "${name}" == "audiobooks" ]] && continue
        mv -- "${entry}" "${TEMP_MOUNT}/audiobooks/"
    done < <(find "${TEMP_MOUNT}" -mindepth 1 -maxdepth 1 -print0)
fi

install -d -o "${owner_uid}" -g "${owner_gid}" -m 0775 \
    "${TEMP_MOUNT}/movies" \
    "${TEMP_MOUNT}/tv" \
    "${TEMP_MOUNT}/.beszel"
sync
umount "${TEMP_MOUNT}"
rmdir "${TEMP_MOUNT}"
TEMP_MOUNT=""

log "Replacing the legacy mount with the canonical storage and bind mounts"
umount "${OLD_MOUNT}"
install -d -m 0755 "${STORAGE_ROOT}" "${OLD_MOUNT}" "${MEDIA_ROOT}/movies" "${MEDIA_ROOT}/tv"

if [[ ! -f "${BACKUP}" ]]; then
    cp --preserve=mode,ownership,timestamps "${FSTAB}" "${BACKUP}"
fi

fstab_temp="$(mktemp "${FSTAB}.homelab.XXXXXX")"
awk -v uuid="${MEDIA_UUID}" \
    '$0 !~ "UUID=" uuid && $2 != "/srv/homelab/media/audiobooks" && $2 != "/srv/homelab/media/movies" && $2 != "/srv/homelab/media/tv" { print }' \
    "${FSTAB}" > "${fstab_temp}"
cat >> "${fstab_temp}" <<EOF

# Homelab external media filesystem and stable service paths.
UUID=${MEDIA_UUID} ${STORAGE_ROOT} ext4 defaults,nofail 0 2
${STORAGE_ROOT}/audiobooks ${MEDIA_ROOT}/audiobooks none bind,nofail,x-systemd.requires-mounts-for=${STORAGE_ROOT} 0 0
${STORAGE_ROOT}/movies ${MEDIA_ROOT}/movies none bind,nofail,x-systemd.requires-mounts-for=${STORAGE_ROOT} 0 0
${STORAGE_ROOT}/tv ${MEDIA_ROOT}/tv none bind,nofail,x-systemd.requires-mounts-for=${STORAGE_ROOT} 0 0
EOF
findmnt --verify --tab-file "${fstab_temp}"
chown root:root "${fstab_temp}"
chmod 0644 "${fstab_temp}"
mv -f "${fstab_temp}" "${FSTAB}"

systemctl daemon-reload
mount -a

[[ "$(findmnt -rn -M "${STORAGE_ROOT}" -o UUID 2>/dev/null || true)" == "${MEDIA_UUID}" ]] || \
    fail "External filesystem mount verification failed."
for directory in audiobooks movies tv; do
    mountpoint -q "${MEDIA_ROOT}/${directory}" || fail "Bind mount verification failed: ${MEDIA_ROOT}/${directory}"
done
[[ -d "${MEDIA_ROOT}/audiobooks/Books" ]] || fail "Audiobook library is not visible after migration."

if docker inspect beszel-agent >/dev/null 2>&1; then
    log "Recreating the monitoring agent against the external filesystem"
    docker compose -f /opt/homelab/services/monitoring/compose.yml \
        --profile agent up -d --force-recreate beszel-agent
fi

log "Restarting media consumers"
restart_services
SERVICES_STOPPED=false

log "Migration complete"
for directory in "${STORAGE_ROOT}" "${MEDIA_ROOT}/audiobooks" "${MEDIA_ROOT}/movies" "${MEDIA_ROOT}/tv"; do
    findmnt -M "${directory}"
done
df -hT "${MEDIA_ROOT}/audiobooks" "${MEDIA_ROOT}/movies" "${MEDIA_ROOT}/tv"
docker ps --filter name=audiobookshelf --filter name=jellyfin \
    --format 'table {{.Names}}\t{{.Status}}'
