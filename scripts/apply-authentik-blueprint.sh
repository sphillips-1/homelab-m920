#!/usr/bin/env sh
set -eu

: "${AUTHENTIK_URL:?AUTHENTIK_URL must be set}"
: "${AUTHENTIK_TOKEN:?AUTHENTIK_TOKEN must be set}"

blueprint_name="${AUTHENTIK_BLUEPRINT_NAME:-homelab-terraform}"
timeout_seconds="${AUTHENTIK_BLUEPRINT_APPLY_TIMEOUT:-300}"
poll_seconds="${AUTHENTIK_BLUEPRINT_POLL_INTERVAL:-5}"
api_url="${AUTHENTIK_URL%/}/api/v3"

auth_header="Authorization: Bearer ${AUTHENTIK_TOKEN}"
started_at="$(date -u +%s)"

blueprints="$(curl --fail-with-body --silent --show-error \
    --get \
    --header 'Accept: application/json' \
    --header "$auth_header" \
    --data-urlencode "name=${blueprint_name}" \
    "${api_url}/managed/blueprints/")"

blueprint_count="$(printf '%s' "$blueprints" | jq --arg name "$blueprint_name" '[.results[] | select(.name == $name)] | length')"
if [ "$blueprint_count" -ne 1 ]; then
  echo "ERROR: Expected exactly one Authentik blueprint named '${blueprint_name}', found ${blueprint_count}." >&2
  exit 1
fi

blueprint_pk="$(printf '%s' "$blueprints" | jq -r --arg name "$blueprint_name" '.results[] | select(.name == $name) | .pk')"
blueprint_url="${api_url}/managed/blueprints/${blueprint_pk}/"

echo "Applying Authentik blueprint '${blueprint_name}' (${blueprint_pk})."
curl --fail-with-body --silent --show-error \
  --request POST \
  --header 'Accept: application/json' \
  --header "$auth_header" \
  "${blueprint_url}apply/" >/dev/null

deadline="$((started_at + timeout_seconds))"
while [ "$(date -u +%s)" -le "$deadline" ]; do
  blueprint="$(curl --fail-with-body --silent --show-error \
    --header 'Accept: application/json' \
    --header "$auth_header" \
    "$blueprint_url")"
  status="$(printf '%s' "$blueprint" | jq -r '.status')"
  last_applied="$(printf '%s' "$blueprint" | jq -r '.last_applied // empty')"

  if [ "$status" = "error" ] || [ "$status" = "orphaned" ]; then
    echo "ERROR: Authentik blueprint apply finished with status '${status}'." >&2
    exit 1
  fi

  if [ -n "$last_applied" ]; then
    last_applied_epoch="$(date -u -d "$last_applied" +%s)"
    if [ "$status" = "successful" ] && [ "$last_applied_epoch" -ge "$started_at" ]; then
      echo "Authentik blueprint '${blueprint_name}' applied successfully at ${last_applied}."
      exit 0
    fi
  fi

  sleep "$poll_seconds"
done

echo "ERROR: Timed out waiting for Authentik blueprint '${blueprint_name}' to apply." >&2
exit 1
