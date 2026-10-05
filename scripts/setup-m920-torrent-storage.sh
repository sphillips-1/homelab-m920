#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
root=/srv/homelab/media/torrents-m920
expected=e440863e-34ce-4c29-b05a-c5dfda01a743
device="/dev/disk/by-uuid/$expected"
[[ -b "$device" ]] || { echo 'Connect the existing torrent USB first.' >&2; exit 1; }
[[ $(blkid -s TYPE -o value "$device") == ext4 ]]
if ! mountpoint -q "$root"; then
    # Do not hide pre-existing downloads beneath the new mount.
    if [[ -d "$root" ]] && find "$root" -mindepth 1 -type f -print -quit | grep -q .; then
        echo "Existing files in $root; migrate them deliberately before mounting." >&2
        exit 1
    fi
    elsewhere=$(findmnt -rn -S "$device" -o TARGET || true)
    [[ -z "$elsewhere" ]] || { echo "USB already mounted at $elsewhere" >&2; exit 1; }
    install -d -m 000 "$root"
    mount -o rw,nodev,nosuid,noexec "$device" "$root"
fi
[[ $(findmnt -n -o UUID -T "$root") == "$expected" ]]
[[ $(findmnt -n -o FSTYPE -T "$root") == ext4 ]]
for directory in complete incomplete; do
    [[ ! -L "$root/$directory" ]] || { echo 'Download directory is a symlink.' >&2; exit 1; }
    install -d -o 1000 -g 1000 -m 0750 "$root/$directory"
done
printf '%s\n' "$expected" > "$root/.homelab-torrent-volume"
chmod 0444 "$root/.homelab-torrent-volume"
chown root:root "$root/.homelab-torrent-volume"
line="UUID=$expected $root ext4 defaults,nofail,nodev,nosuid,noexec,x-systemd.device-timeout=10s 0 2"
if ! grep -Fqx "$line" /etc/fstab; then
    if grep -Eq "^[^#].*($expected|[[:space:]]$root[[:space:]])" /etc/fstab; then
        echo 'Conflicting fstab entry; refusing to overwrite it.' >&2; exit 1
    fi
    cp -a /etc/fstab "/etc/fstab.before-torrent-usb-$(date +%Y%m%d-%H%M%S)"
    printf '\n%s\n' "$line" >> /etc/fstab
    systemctl daemon-reload
fi
bash /opt/homelab/scripts/check-m920-torrent-storage.sh
echo 'Existing torrent USB mounted and verified; files preserved.'
