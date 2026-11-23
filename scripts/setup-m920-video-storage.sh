#!/usr/bin/env bash
set -euo pipefail

storage=/srv/homelab/storage
source_dir=$storage/video-data
target=/srv/homelab/video-data
uuid=4c746df8-53bf-4717-a4ce-40b3b7e90ed2
fstab=/etc/fstab
line="$source_dir $target none bind,nofail,x-systemd.requires-mounts-for=$storage 0 0"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || fail 'Root is required to configure the persistent bind mount.'
exec 9>/run/lock/homelab-video-storage.lock
flock -x 9

[[ $(findmnt -rn -M "$storage" -o UUID,FSTYPE) == "$uuid ext4" ]] ||
    fail 'The expected ext4 SSD is not mounted at the storage root.'
options=$(findmnt -rn -M "$storage" -o OPTIONS)
[[ ,$options, == *,rw,* ]] || fail 'The media SSD is not writable.'
[[ $(stat -c %d "$storage") != $(stat -c %d /) ]] ||
    fail 'The storage root is on the internal filesystem.'

configured=$(awk -v target="$target" '$1 !~ /^#/ && $2 == target { print }' "$fstab")
[[ -z $configured || $configured == "$line" ]] ||
    fail 'A conflicting video-data entry exists in fstab.'

check_path() {
    [[ ! -L $1 && ( ! -e $1 || -d $1 ) ]] ||
        fail "Expected a real directory at $1."
}

verify_mount() {
    [[ $(findmnt -rn -M "$target" -o UUID,FSTYPE) == "$uuid ext4" &&
       $(stat -c '%d:%i' "$source_dir") == "$(stat -c '%d:%i' "$target")" ]] ||
        fail 'The video-data mount does not point to the expected SSD directory.'
}

check_path "$target"
check_path "$source_dir"
if mountpoint -q "$target"; then
    verify_mount
elif [[ -d $target ]]; then
    [[ -z $(find "$target" -mindepth 1 -maxdepth 1 -print -quit) ]] ||
        fail 'Refusing to hide existing files beneath the video-data mount.'
    [[ $(stat -c '%u:%g:%a' "$target") == 0:0:0 ]] ||
        fail 'An existing unmounted target must be root-owned with mode 000.'
else
    install -d -o root -g root -m 000 "$target"
fi

for relative in '' /downloads /downloads/incomplete /downloads/complete /media /media/movies /media/tv /media/music; do
    directory=$source_dir$relative
    check_path "$directory"
    [[ $(findmnt -rn -T "${directory%/*}" -o TARGET) == "$storage" ]] ||
        fail "Unexpected filesystem above $directory."
    if [[ -d $directory ]]; then
        [[ $(findmnt -rn -T "$directory" -o TARGET) == "$storage" ]] ||
            fail "Unexpected filesystem at $directory."
        [[ $(stat -c '%u:%g' "$directory") == 1000:1000 ]] ||
            fail "Unexpected ownership at $directory."
    else
        install -d -o 1000 -g 1000 -m 0750 "$directory"
    fi
done

if ! mountpoint -q "$target"; then
    mount --bind "$source_dir" "$target"
fi
verify_mount

if [[ -z $configured ]]; then
    backup=$(mktemp /etc/fstab.before-video-data.XXXXXX)
    cp -a "$fstab" "$backup"
    staged=$(mktemp /etc/fstab.video-data.XXXXXX)
    trap 'rm -f -- "$staged"' EXIT
    cp -a "$fstab" "$staged"
    printf '\n%s\n' "$line" >> "$staged"
    cmp -s "$fstab" "$backup" || fail 'fstab changed during setup. Retry after reviewing it.'
    mv -T "$staged" "$fstab"
fi
systemctl daemon-reload
findmnt -M "$target" -o TARGET,SOURCE,FSTYPE,UUID,OPTIONS
