#!/bin/bash
set -euo pipefail
# Docker restart policies and manual Compose starts must also fail closed.
expected=e440863e-34ce-4c29-b05a-c5dfda01a743
[[ $(stat -c %d /downloads) != $(stat -c %d /config) ]] || {
    echo 'Refusing to download to the M920 system filesystem.' >&2; exit 1;
}
[[ $(cat /downloads/.homelab-torrent-volume) == "$expected" ]] || {
    echo 'Torrent USB identity marker missing or incorrect.' >&2; exit 1;
}
for directory in complete incomplete; do
    [[ -d "/downloads/$directory" && ! -L "/downloads/$directory" ]] || exit 1
done
exec /init
