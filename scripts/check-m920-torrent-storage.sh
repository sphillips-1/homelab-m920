#!/usr/bin/env bash
set -euo pipefail
root=/srv/homelab/media/torrents-m920
expected=e440863e-34ce-4c29-b05a-c5dfda01a743
mountpoint -q "$root" || { echo 'M920 torrent USB is not mounted.' >&2; exit 1; }
[[ $(findmnt -n -o UUID -T "$root") == "$expected" ]] || {
    echo 'Unexpected M920 torrent filesystem UUID.' >&2; exit 1;
}
[[ $(findmnt -n -o FSTYPE -T "$root") == ext4 ]]
options=$(findmnt -n -o OPTIONS -T "$root")
[[ ,$options, == *,rw,* ]]
[[ $(stat -c %d "$root") != $(stat -c %d /) ]]
for directory in complete incomplete; do
    [[ -d "$root/$directory" && ! -L "$root/$directory" ]]
done
[[ $(cat "$root/.homelab-torrent-volume") == "$expected" ]]
