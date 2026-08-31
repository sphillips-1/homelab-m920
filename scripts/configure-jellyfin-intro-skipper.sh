#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
SERVICE_DIR="${REPO_DIR}/services/jellyfin"
ENV_FILE="${SERVICE_DIR}/.intro-skipper.env"
REPOSITORY_URL="https://intro-skipper.org/manifest.json"
JELLYFIN_LAN_IP="$(sed -n 's/^JELLYFIN_LAN_IP=//p' "${SERVICE_DIR}/.env")"
[[ -n "${JELLYFIN_LAN_IP}" ]] || { echo "ERROR: Jellyfin LAN address is not configured." >&2; exit 1; }
API_BASE="http://${JELLYFIN_LAN_IP}:8096"

fail() { echo "ERROR: $1" >&2; exit 1; }
api() {
    local method="$1" path="$2"
    shift 2
    curl --fail --silent --show-error -X "${method}" \
        -H "X-Emby-Token: ${JELLYFIN_API_KEY}" "$@" "${API_BASE}${path}"
}
wait_healthy() {
    local deadline=$((SECONDS + 180))
    while (( SECONDS < deadline )); do
        if [[ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' jellyfin 2>/dev/null || true)" == "healthy" ]]; then
            return 0
        fi
        sleep 3
    done
    fail "Jellyfin did not become healthy within 180 seconds."
}

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ -f "${ENV_FILE}" ]] || fail "Missing ${ENV_FILE}; copy .intro-skipper.env.example, add a dedicated Jellyfin API key, and set mode 0600."
[[ "$(stat -c '%a' "${ENV_FILE}")" == "600" ]] || fail "${ENV_FILE} must have mode 0600."
# shellcheck disable=SC1090
source "${ENV_FILE}"
[[ -n "${JELLYFIN_API_KEY:-}" && "${JELLYFIN_API_KEY}" != REPLACE_* ]] || fail "JELLYFIN_API_KEY is not configured."
docker inspect jellyfin >/dev/null 2>&1 || fail "The jellyfin container does not exist."
wait_healthy

version="$(api GET /System/Info | python3 -c 'import json,sys; print(json.load(sys.stdin)["Version"])')"
python3 - "${version}" <<'PY' || fail "Jellyfin ${version} is unsupported; Intro Skipper requires 10.11.8 or newer."
import sys
parts = tuple(int(x) for x in sys.argv[1].split(".")[:3])
raise SystemExit(0 if parts >= (10, 11, 8) and parts < (10, 12, 0) else 1)
PY

ffmpeg="/usr/lib/jellyfin-ffmpeg/ffmpeg"
ffmpeg_version="$(docker exec jellyfin "${ffmpeg}" -version 2>&1 | sed -n '1s/^ffmpeg version \([^ ]*\).*/\1/p')"
python3 - "${ffmpeg_version}" <<'PY' || fail "The bundled Jellyfin FFmpeg (${ffmpeg_version:-unknown}) is older than required version 7.1.1-7."
import re, sys
match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(\d+))?", sys.argv[1])
if not match:
    raise SystemExit(1)
major, minor, patch = (int(value) for value in match.groups()[:3])
build = int(match.group(4) or 0)
supported = (major, minor, patch) > (7, 1, 1) or ((major, minor, patch) == (7, 1, 1) and build >= 7)
raise SystemExit(0 if supported else 1)
PY
ffmpeg_buildconf="$(docker exec jellyfin "${ffmpeg}" -buildconf 2>&1)"
grep -q -- '--enable-chromaprint' <<<"${ffmpeg_buildconf}" || \
    fail "The bundled Jellyfin FFmpeg does not advertise Chromaprint support."

repositories_file="$(mktemp)"
merged_file="$(mktemp)"
cleanup() { rm -f "${repositories_file}" "${merged_file}"; }
trap cleanup EXIT
api GET /Repositories > "${repositories_file}"
python3 - "${repositories_file}" "${merged_file}" "${REPOSITORY_URL}" <<'PY'
import json, sys
source, target, url = sys.argv[1:]
with open(source, encoding="utf-8") as handle:
    repos = json.load(handle)
matches = [repo for repo in repos if repo.get("Url", "").rstrip("/") == url.rstrip("/")]
if matches:
    matches[0]["Enabled"] = True
    repos = [repo for repo in repos if repo not in matches[1:]]
else:
    repos.append({"Name": "Intro Skipper", "Url": url, "Enabled": True})
with open(target, "w", encoding="utf-8") as handle:
    json.dump(repos, handle, separators=(",", ":"))
PY
if ! python3 - "${repositories_file}" "${merged_file}" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as left, open(sys.argv[2], encoding="utf-8") as right:
    raise SystemExit(0 if json.load(left) == json.load(right) else 1)
PY
then
    api POST /Repositories -H 'Content-Type: application/json' --data-binary "@${merged_file}" >/dev/null
    echo "Registered the Intro Skipper plugin repository."
else
    echo "Intro Skipper plugin repository is already registered and enabled."
fi

plugins="$(api GET /Plugins)"
if python3 -c 'import json,sys; raise SystemExit(0 if any(p.get("Name")=="Intro Skipper" for p in json.load(sys.stdin)) else 1)' <<<"${plugins}"; then
    echo "Intro Skipper is already installed."
else
    api POST '/Packages/Installed/Intro%20Skipper' >/dev/null
    echo "Installed Intro Skipper; restarting Jellyfin to load it."
    docker restart jellyfin >/dev/null
    wait_healthy
fi

plugins="$(api GET /Plugins)"
plugin_id="$(python3 -c 'import json,sys; print(next((p["Id"] for p in json.load(sys.stdin) if p.get("Name")=="Intro Skipper" and p.get("Status")=="Active"), ""))' <<<"${plugins}")"
[[ -n "${plugin_id}" ]] || fail "Intro Skipper is not active after installation. Check docker logs jellyfin."

configuration="$(api GET "/Plugins/${plugin_id}/Configuration")"
desired="$(python3 -c '
import json,sys
c=json.load(sys.stdin)
c.update({"AutoDetectIntros":True,"UpdateMediaSegments":True,"ScanIntroduction":True,"ScanCredits":True,"ScanRecap":True,"ScanPreview":False,"ScanCommercial":False,"MaxParallelism":1,"ProcessPriority":"BelowNormal","CacheFingerprints":True})
print(json.dumps(c,separators=(",",":")))
' <<<"${configuration}")"
if ! python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1]) == json.loads(sys.argv[2]) else 1)' "${configuration}" "${desired}"; then
    api POST "/Plugins/${plugin_id}/Configuration" -H 'Content-Type: application/json' --data-binary "${desired}" >/dev/null
    echo "Configured conservative Intro, Credits, and Recap detection with one below-normal-priority worker."
else
    echo "Intro Skipper settings already match the repository-managed policy."
fi

echo "Jellyfin ${version}, Intro Skipper, Media Segments, FFmpeg, and Chromaprint are ready."
