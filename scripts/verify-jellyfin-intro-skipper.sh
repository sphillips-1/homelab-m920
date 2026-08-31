#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
ENV_FILE="${REPO_DIR}/services/jellyfin/.intro-skipper.env"
EPISODE_ID="${1:-}"

fail() { echo "ERROR: $1" >&2; exit 1; }
[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ -f "${ENV_FILE}" ]] || fail "Missing ${ENV_FILE}."
# shellcheck disable=SC1090
source "${ENV_FILE}"
ip="$(sed -n 's/^JELLYFIN_LAN_IP=//p' "${REPO_DIR}/services/jellyfin/.env")"
[[ -n "${ip}" && -n "${JELLYFIN_API_KEY:-}" ]] || fail "Jellyfin URL or API key is not configured."
base="http://${ip}:8096"

health="$(docker inspect --format '{{.State.Status}} {{.State.Health.Status}} restarts={{.RestartCount}}' jellyfin)"
echo "Jellyfin: ${health}"
curl --fail --silent --show-error -H "X-Emby-Token: ${JELLYFIN_API_KEY}" "${base}/Plugins" | python3 -c '
import json,sys
p=next((x for x in json.load(sys.stdin) if x.get("Name")=="Intro Skipper"),None)
if not p: raise SystemExit("Intro Skipper is not installed")
print("Plugin: %s (%s)" % (p.get("Version"),p.get("Status")))
'
curl --fail --silent --show-error -H "X-Emby-Token: ${JELLYFIN_API_KEY}" "${base}/ScheduledTasks" | python3 -c '
import json,sys
t=next((x for x in json.load(sys.stdin) if x.get("Name") in ("Detect and Analyze Media Segments","Detect and Analyze")),None)
if not t: raise SystemExit("Intro Skipper analysis task is missing")
last=t.get("LastExecutionResult") or {}
print("Task: %s; progress=%s; last=%s" % (t.get("State"),t.get("CurrentProgressPercentage"),last.get("Status")))
'

if [[ -n "${EPISODE_ID}" ]]; then
    curl --fail --silent --show-error -H "X-Emby-Token: ${JELLYFIN_API_KEY}" \
        "${base}/MediaSegments/${EPISODE_ID}" | python3 -c '
import json,sys
d=json.load(sys.stdin)
items=d.get("Items",[]) if isinstance(d,dict) else d
print("Segments:",len(items),[x.get("Type") for x in items])
'
else
    echo "Segments: not checked (pass a Jellyfin episode ID to this script)."
fi
