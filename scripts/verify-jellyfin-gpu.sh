#!/usr/bin/env bash
set -euo pipefail

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
docker inspect jellyfin >/dev/null 2>&1 || fail "The jellyfin container does not exist."

render_device="$(docker inspect --format '{{range .HostConfig.Devices}}{{if eq .PathInContainer .PathOnHost}}{{.PathInContainer}}{{end}}{{end}}' jellyfin)"
[[ -n "${render_device}" ]] || fail "No identically mapped render device was found in the container configuration."
[[ -c "${render_device}" ]] || fail "Host render device ${render_device} is missing."

echo "==> Host GPU"
ls -l /dev/dri
if command -v intel_gpu_top >/dev/null 2>&1; then
    intel_gpu_top -L
fi

echo "==> Container device and permissions"
docker exec jellyfin ls -l "${render_device}"
docker exec jellyfin test -r "${render_device}" || fail "Jellyfin cannot read ${render_device}."
docker exec jellyfin test -w "${render_device}" || fail "Jellyfin cannot write ${render_device}."
docker exec jellyfin id

echo "==> VA-API driver and supported codec entry points"
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/vainfo --display drm --device "${render_device}"

echo "==> QSV initialization over VA-API"
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/ffmpeg \
    -hide_banner -loglevel verbose \
    -init_hw_device "vaapi=va:${render_device},driver=iHD" \
    -init_hw_device qsv=qs@va \
    -f lavfi -i color=size=64x64:rate=1 \
    -frames:v 1 -f null -

echo "Jellyfin render-device permissions, VA-API discovery, and QSV initialization passed."
