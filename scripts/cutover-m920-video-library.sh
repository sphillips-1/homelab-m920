#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
live=/opt/homelab/services
ssd=/srv/homelab/storage
video=/srv/homelab/video-data/media
bash "$repo/scripts/check-m920-video-storage.sh"
[[ ! -L "$video/.jellyfin-imports" ]]
install -d -m 0750 "$video/.jellyfin-imports"

export JELLYFIN_LAN_IP JELLYFIN_RENDER_DEVICE JELLYFIN_RENDER_GID
JELLYFIN_LAN_IP=$(docker inspect --format '{{(index (index .HostConfig.PortBindings "8096/tcp") 0).HostIp}}' jellyfin)
JELLYFIN_RENDER_DEVICE=$(docker inspect --format '{{(index .HostConfig.Devices 0).PathOnHost}}' jellyfin)
JELLYFIN_RENDER_GID=$(docker inspect --format '{{index .HostConfig.GroupAdd 0}}' jellyfin)

umask 077
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
# Keep the current importer's runtime environment private while reusing the
# live Compose project and its bind-mounted application code.
docker inspect --format '{{json .Config.Env}}' audiobook-importer |
    python3 -c 'import json,sys
for entry in json.load(sys.stdin):
    if "\n" in entry or "\r" in entry:
        raise SystemExit("Cannot safely serialize multiline importer environment")
    print(entry)' > "$work/importer.env"
cat > "$work/env.yml" <<'YAML'
services:
  audiobook-importer:
    env_file: !override
      - path: ${CUTOVER_IMPORTER_ENV}
        format: raw
YAML
export CUTOVER_IMPORTER_ENV="$work/importer.env"

jellyfin=(docker compose --env-file /dev/null -p jellyfin -f "$live/jellyfin/compose.yml")
new_jellyfin=("${jellyfin[@]}" -f "$repo/services/jellyfin/compose.video.yml")
importer=(docker compose -p qbittorrent-m920 -f "$live/qbittorrent-m920/compose.yml" -f "$work/env.yml")
new_importer=("${importer[@]}" -f "$repo/services/qbittorrent-m920/compose.video.yml")
"${new_jellyfin[@]}" config --quiet
"${new_importer[@]}" config --quiet

rollback() {
    trap - ERR
    echo 'Cutover failed. Restoring the previous importer and Jellyfin library mounts.' >&2
    "${importer[@]}" up -d --no-deps --wait --wait-timeout 90 audiobook-importer || true
    "${jellyfin[@]}" up -d --no-deps --wait --wait-timeout 90 jellyfin || true
    exit 1
}
trap rollback ERR
"${importer[@]}" stop audiobook-importer
[[ -z $(find "$ssd/.jellyfin-imports" -mindepth 1 -maxdepth 1 -print -quit) ]]
python3 - "$ssd" "$video" <<'PY'
import os
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
for kind in ("movies", "tv"):
    for path in (source / kind).rglob("*"):
        relative = path.relative_to(source)
        if any(part.startswith(".") for part in relative.parts):
            continue
        mirror = target / relative
        if path.is_symlink() or mirror.is_symlink():
            raise SystemExit(f"Unexpected link at {relative}")
        if path.is_dir():
            if not mirror.is_dir():
                raise SystemExit(f"Missing staged directory at {relative}")
        elif not path.is_file() or not mirror.is_file() or not os.path.samefile(path, mirror):
            raise SystemExit(f"Missing or inconsistent staged file at {relative}")
PY
"${new_jellyfin[@]}" up -d --no-deps --wait --wait-timeout 90 jellyfin
"${new_importer[@]}" up -d --no-deps --wait --wait-timeout 90 audiobook-importer

[[ $(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/media/movies"}}{{.Source}} {{.RW}}{{end}}{{end}}' jellyfin) == "$video/movies false" ]]
[[ $(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/media/tv"}}{{.Source}} {{.RW}}{{end}}{{end}}' jellyfin) == "$video/tv false" ]]
[[ $(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/jellymedia"}}{{.Source}}{{end}}{{end}}' audiobook-importer) == "$video" ]]
trap - ERR
echo 'Jellyfin and the video importer now share the consolidated SSD library.'
