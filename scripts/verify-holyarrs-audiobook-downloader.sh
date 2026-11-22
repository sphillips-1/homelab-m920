#!/usr/bin/env bash
set -euo pipefail

token=$(sed -n 's/^HOLYARRS_AUDIOBOOK_QBIT_KEY=//p' /srv/homelab/appdata/holyarrs-audiobooks/client.env)
[[ "$token" =~ ^[a-f0-9]{64}$ ]]
base=http://127.0.0.1:8093/api/v2
[[ $(docker exec m920-qbittorrent curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "$base/torrents/info") == 403 ]]
printf 'Authorization: Bearer %s\n' "$token" |
    docker exec -i m920-qbittorrent curl -fsS --max-time 10 -H @- "$base/torrents/info" |
    python3 -c 'import json, sys; assert isinstance(json.load(sys.stdin), list)'
catalog='http://127.0.0.1:8093/internal/audiobook-library?page=0'
[[ $(docker exec m920-qbittorrent curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "$catalog") == 403 ]]
printf 'Authorization: Bearer %s\n' "$token" |
    docker exec -i m920-qbittorrent curl -fsS --max-time 20 -H @- "$catalog" |
    python3 -c 'import json, sys; result = json.load(sys.stdin); assert isinstance(result["items"], list); print("Verified HolyArrs catalog access for", result["total"], "audiobooks.")'
