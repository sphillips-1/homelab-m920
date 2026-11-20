#!/usr/bin/env bash
set -euo pipefail

storage=/srv/homelab/storage
root=/srv/homelab/video-data
uuid=4c746df8-53bf-4717-a4ce-40b3b7e90ed2

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ $(findmnt -rn -M "$root" -o UUID,FSTYPE) == "$uuid ext4" ]] ||
    fail 'The video-data bind mount is missing or on the wrong filesystem.'
[[ $(stat -Lc '%d:%i' "$root") == "$(stat -Lc '%d:%i' "$storage/video-data")" ]] ||
    fail 'The bind mount does not point to the expected SSD directory.'
options=$(findmnt -rn -M "$root" -o OPTIONS)
[[ ,$options, == *,rw,* ]] || fail 'The video-data mount is read-only.'

for path in downloads downloads/incomplete downloads/complete media media/movies media/tv; do
    directory=$root/$path
    [[ -d $directory && ! -L $directory &&
       $(findmnt -rn -T "$directory" -o TARGET) == "$root" ]] ||
        fail "Missing directory or unexpected mount at $directory."
done
