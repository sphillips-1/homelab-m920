#!/usr/bin/env bash
set -euo pipefail
umask 077

root=/srv/homelab
repo=/opt/homelab
library=$root/media/audiobooks
old=$root/storage/audiobooks
new=$root/storage/video-data/media/audiobooks
visible=$root/video-data/media/audiobooks
uuid=4c746df8-53bf-4717-a4ce-40b3b7e90ed2
db=$root/appdata/audiobookshelf/absdatabase.sqlite
abs=(docker compose -f "$repo/services/audiobookshelf/compose.yml")
importer=(docker compose -f "$repo/services/qbittorrent-m920/compose.yml")

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
identity() { stat -Lc '%d:%i' "$1"; }
fstab_source() { awk -v target="$library" '$1 !~ /^#/ && $2 == target {print $1}' /etc/fstab; }
find_uuid() { findmnt -rn -T "$1" -o UUID; }

[[ $EUID -eq 0 ]] || fail 'Run as root through the deployment workflow.'
bash "$repo/scripts/check-m920-video-storage.sh"
[[ $(findmnt -rn -M "$library" -o UUID) == "$uuid" ]] || fail 'Audiobook bind is missing or on the wrong filesystem.'
if [[ $(fstab_source) == "$new" && -d $new && -d $old ]] &&
    [[ $(identity "$library") == "$(identity "$visible")" ]]; then
    echo 'Audiobook storage is already consolidated.'
    exit 0
fi
[[ $(fstab_source) == "$old" && -d $old && ! -L $old &&
   ! -e $new && ! -L $new && $(identity "$library") == "$(identity "$old")" ]] ||
    fail 'Existing audiobook or destination layout differs from the expected pre-migration state.'
[[ $(find_uuid "$old") == "$uuid" && $(find_uuid "${new%/*}") == "$uuid" &&
   $(stat -Lc '%d' "$old") == "$(stat -Lc '%d' "${new%/*}")" ]] ||
    fail 'The source and target are not on the same ext4 filesystem.'
[[ -d $old/Books && ! -L $old/Books && -f $db && ! -L $db ]] ||
    fail 'Audiobook files or Audiobookshelf database are missing.'

check_import_idle() {
    [[ -z $(find "$library/.audiobook-imports" -mindepth 1 -print -quit) ]] ||
        fail 'The audiobook staging directory is not empty.'
    python3 - "$root/appdata/audiobook-importer/imports.sqlite" <<'PY'
import sqlite3
import sys
with sqlite3.connect(f'file:{sys.argv[1]}?mode=ro', uri=True) as db:
    if db.execute("SELECT 1 FROM jobs WHERE status='copying' LIMIT 1").fetchone():
        raise SystemExit('A media import is still copying.')
PY
}

snapshot() {
    python3 - "$db" "$1" <<'PY'
import json
import sqlite3
import sys
with sqlite3.connect(f'file:{sys.argv[1]}?mode=ro', uri=True) as db:
    db.execute('BEGIN')
    roots = [r[0] for r in db.execute('SELECT path FROM libraryFolders ORDER BY id')]
    items = db.execute("SELECT id,path,coalesce(isMissing,0),coalesce(isInvalid,0) FROM libraryItems WHERE mediaType='book' ORDER BY id").fetchall()
    progress = db.execute("SELECT id,mediaItemId,userId FROM mediaProgresses ORDER BY id").fetchall()
if roots != ['/audiobooks'] or not items or any(not p.startswith('/audiobooks/') for _,p,_,_ in items):
    raise SystemExit('Unexpected Audiobookshelf library roots or item paths.')
with open(sys.argv[2], 'w') as file:
    json.dump({'roots': roots, 'items': items, 'progress': progress}, file)
PY
}

verify_container_paths() {
    docker exec -i audiobookshelf node -e '
const fs = require("node:fs");
const {items} = JSON.parse(fs.readFileSync(0, "utf8"));
const paths = items.filter(([, , missing, invalid]) => !missing && !invalid).map(([, path]) => path);
const unreadable = paths.filter(path => { try { fs.accessSync(path, fs.constants.R_OK); return false } catch { return true } });
if (unreadable.length) throw new Error(unreadable.length + " Audiobookshelf catalog paths are unreadable");
console.log("Verified " + paths.length + " readable audiobook item paths.");
' < "$1"
}

check_import_idle
backup=$(mktemp -d "$root/backups/audiobook-cutover.XXXXXXXX")
retained=$(mktemp -d "$root/storage/.audiobooks-retained.XXXXXXXX")
fstab_tmp=''
stopped=false
committed=false
old_inode=$(identity "$old")
cp --preserve=all /etc/fstab "$backup/fstab"

restore_mount() {
    local result=$?
    local rollback_status
    trap - EXIT
    if [[ $committed != true && $stopped == true ]]; then
        set +e
        echo 'Cutover failed. Restoring the original audiobook mount.' >&2
        (
            set -e
            "${importer[@]}" stop -t 60 audiobook-importer
            "${abs[@]}" stop -t 60 audiobookshelf
            if [[ -d $new && $(identity "$new") == "$old_inode" ]]; then
                if mountpoint -q "$library"; then umount "$library"; fi
                if [[ -d $old && ! -e $retained ]]; then mv -T -- "$old" "$retained"; fi
                [[ ! -e $old ]]
                mv -T -- "$new" "$old"
            fi
            cp --preserve=all "$backup/fstab" /etc/fstab
            systemctl daemon-reload
            if ! mountpoint -q "$library"; then mount "$library"; fi
            [[ $(identity "$library") == "$old_inode" ]]
            "${abs[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 audiobookshelf
            "${importer[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 audiobook-importer
        )
        rollback_status=$?
        if (( rollback_status != 0 )); then
            echo "ERROR: Automatic rollback failed. Recovery evidence is in $backup." >&2
            result=1
        fi
    fi
    if [[ -n $fstab_tmp && -f $fstab_tmp ]]; then rm -f -- "$fstab_tmp"; fi
    exit "$result"
}
trap restore_mount EXIT

echo 'Staging a hard-linked rollback tree while Audiobookshelf is online.'
rsync -aH --link-dest="$old" "$old/" "$retained/"
snapshot "$backup/preflight.json"
verify_container_paths "$backup/preflight.json"

check_import_idle
stopped=true
"${importer[@]}" stop -t 60 audiobook-importer
check_import_idle
"${abs[@]}" stop -t 60 audiobookshelf
snapshot "$backup/before.json"
tar -C "$root/appdata/audiobookshelf" -cf "$backup/audiobookshelf-appdata.tar" .
tar -tf "$backup/audiobookshelf-appdata.tar" > "$backup/archive-manifest"
grep -Fx './absdatabase.sqlite' "$backup/archive-manifest" >/dev/null
rsync -aH --delete --link-dest="$old" "$old/" "$retained/"

python3 - "$old" "$retained" <<'PY'
from pathlib import Path
import sys

source, rollback = map(Path, sys.argv[1:])
count = 0
for entry in source.rglob('*'):
    saved = rollback / entry.relative_to(source)
    if entry.is_symlink():
        if not saved.is_symlink() or entry.readlink() != saved.readlink():
            raise SystemExit('Rollback symlink verification failed.')
    elif entry.is_file():
        if not saved.is_file() or not entry.samefile(saved):
            raise SystemExit('Rollback file inode verification failed.')
        count += 1
    elif not entry.is_dir() or not saved.is_dir():
        raise SystemExit('Unexpected filesystem entry in the audiobook library.')
if not count:
    raise SystemExit('Rollback verification found no audiobook files.')
print(f'Verified {count} hard-linked rollback files.')
PY

fstab_tmp=$(mktemp /etc/.fstab.audiobooks.XXXXXXXX)
awk -v from="$old" -v to="$new" -v target="$library" '
    $1 == from && $2 == target { sub(/^[^[:space:]]+/, to); count++ }
    { print }
    END { if (count != 1) exit 1 }
' /etc/fstab > "$fstab_tmp"
chmod --reference=/etc/fstab "$fstab_tmp"
chown --reference=/etc/fstab "$fstab_tmp"
[[ $(findmnt --fstab --tab-file "$fstab_tmp" -rn -M "$library" -o SOURCE) == "$new" ]] ||
    fail 'The replacement fstab entry could not be verified.'

umount "$library"
mv -T -- "$old" "$new"
mv -T -- "$retained" "$old"
mv -T -- "$fstab_tmp" /etc/fstab
systemctl daemon-reload
mount "$library"
[[ $(findmnt -rn -M "$library" -o UUID) == "$uuid" &&
   $(identity "$library") == "$old_inode" &&
   $(identity "$library") == "$(identity "$visible")" ]] ||
    fail 'The new audiobook bind did not preserve the original library inode.'

"${abs[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 audiobookshelf
snapshot "$backup/after.json"
verify_container_paths "$backup/after.json"
python3 - "$backup/before.json" "$backup/after.json" <<'PY'
import json
from pathlib import Path
import sys

before, after = [json.loads(Path(path).read_text()) for path in sys.argv[1:]]
if before['roots'] != after['roots'] or before['items'] != after['items']:
    raise SystemExit('Audiobookshelf catalog IDs, paths, or availability changed.')
if not {tuple(row) for row in before['progress']} <= {tuple(row) for row in after['progress']}:
    raise SystemExit('An existing listening progress record is missing.')
print(f"Preserved {len(before['items'])} catalog items and {len(before['progress'])} progress records.")
PY
"${importer[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 120 audiobook-importer
bash "$repo/scripts/verify-torrent-connectivity.sh"
committed=true
echo "Audiobook storage consolidated at $visible. Retained rollback tree: $old. Backup: $backup."
