#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"
ENV_FILE="${REPO_DIR}/services/jellyfin/.intro-skipper.env"
JELLYFIN_LAN_IP="$(sed -n 's/^JELLYFIN_LAN_IP=//p' "${REPO_DIR}/services/jellyfin/.env")"
[[ -n "${JELLYFIN_LAN_IP}" ]] || { echo "ERROR: Jellyfin LAN address is not configured." >&2; exit 1; }
API_BASE="http://${JELLYFIN_LAN_IP}:8096"

fail() { echo "ERROR: $1" >&2; exit 1; }
[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ -f "${ENV_FILE}" ]] || fail "Missing ${ENV_FILE}; see services/jellyfin/README.md."
[[ "$(stat -c '%a' "${ENV_FILE}")" == "600" ]] || fail "${ENV_FILE} must have mode 0600."
# shellcheck disable=SC1090
source "${ENV_FILE}"
[[ -n "${JELLYFIN_API_KEY:-}" ]] || fail "JELLYFIN_API_KEY is empty."
[[ "$(docker inspect --format '{{.State.Health.Status}}' jellyfin 2>/dev/null || true)" == "healthy" ]] || fail "Jellyfin is not healthy."

tasks="$(curl --fail --silent --show-error -H "X-Emby-Token: ${JELLYFIN_API_KEY}" "${API_BASE}/ScheduledTasks")"
read -r task_id task_state < <(python3 -c '
import json,sys
tasks=json.load(sys.stdin)
t=next((x for x in tasks if x.get("Name") in ("Detect and Analyze Media Segments","Detect and Analyze")),None)
if not t: raise SystemExit(1)
print(t["Id"],t.get("State","Idle"))
' <<<"${tasks}") || fail "The Intro Skipper analysis task was not found; confirm the plugin is active."

if [[ "${task_state}" == "Running" ]]; then
    echo "Intro Skipper analysis is already running (task ${task_id}); no duplicate run was started."
    exit 0
fi
curl --fail --silent --show-error -X POST -H "X-Emby-Token: ${JELLYFIN_API_KEY}" \
    "${API_BASE}/ScheduledTasks/Running/${task_id}" >/dev/null
echo "Started Intro Skipper 'Detect and Analyze Media Segments' task ${task_id}."
echo "Follow progress in Dashboard -> Scheduled Tasks or with: docker logs -f jellyfin"
echo "This operation only analyzes media and writes Jellyfin metadata; it does not delete library metadata."
