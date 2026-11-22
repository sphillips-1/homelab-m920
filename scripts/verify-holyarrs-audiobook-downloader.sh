#!/usr/bin/env bash
set -euo pipefail

token=$(sed -n 's/^HOLYARRS_AUDIOBOOK_QBIT_KEY=//p' /srv/homelab/appdata/holyarrs-audiobooks/client.env)
[[ "$token" =~ ^[a-f0-9]{64}$ ]]
base=http://127.0.0.1:8093/api/v2
[[ $(docker exec m920-qbittorrent curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "$base/torrents/info") == 403 ]]
printf 'Authorization: Bearer %s\n' "$token" |
    docker exec -i m920-qbittorrent curl -fsS --max-time 10 -H @- "$base/torrents/info" |
    python3 -c 'import json, sys; assert isinstance(json.load(sys.stdin), list)'
