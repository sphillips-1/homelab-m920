#!/usr/bin/env bash
set -euo pipefail
umask 077

state=/srv/homelab/appdata/holyarrs-audiobooks
[[ ! -L "$state" ]]
install -d -o root -g root -m 0700 "$state"
if [[ -f "$state/client.env" ]]; then
    token=$(sed -n 's/^HOLYARRS_AUDIOBOOK_QBIT_KEY=//p' "$state/client.env")
    [[ "$token" =~ ^[a-f0-9]{64}$ ]]
else
    token=$(openssl rand -hex 32)
    printf 'HOLYARRS_AUDIOBOOK_QBIT_KEY=%s\n' "$token" > "$state/client.env.new"
    mv -T "$state/client.env.new" "$state/client.env"
fi
printf '"Bearer %s" 1;\n' "$token" > "$state/bearer.conf.new"
mv -T "$state/bearer.conf.new" "$state/bearer.conf"
