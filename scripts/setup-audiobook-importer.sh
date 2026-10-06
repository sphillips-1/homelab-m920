#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
root=/srv/homelab
expected=4c746df8-53bf-4717-a4ce-40b3b7e90ed2
for directory in "$root/storage" "$root/media/audiobooks/Books"; do
    [[ -d "$directory" && ! -L "$directory" ]]
    [[ $(findmnt -n -o UUID -T "$directory") == "$expected" ]] || {
        echo 'Audiobook library filesystem is unavailable.' >&2; exit 1;
    }
done
[[ ! -L "$root/storage/.audiobook-imports" ]]
install -d -o 1000 -g 1000 -m 0750 "$root/storage/.audiobook-imports" \
    "$root/appdata/audiobook-importer"
