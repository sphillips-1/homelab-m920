#!/usr/bin/env bash
set -euo pipefail

AUDIOBOOK_ROOT="/srv/homelab/media/audiobooks"
BOOKS_ROOT="${AUDIOBOOK_ROOT}/Books"

if [[ "${EUID}" -ne 0 ]]; then
echo "ERROR: Run this script as root."
exit 1
fi

if [[ ! -d "${BOOKS_ROOT}" ]]; then
echo "ERROR: Audiobook Books directory does not exist:"
echo " ${BOOKS_ROOT}"
exit 1
fi

echo "==> Creating Audiobookshelf compatibility links"
echo
echo "Source:"
echo " ${BOOKS_ROOT}"
echo
echo "Link root:"
echo " ${AUDIOBOOK_ROOT}"
echo

created=0
existing=0

while IFS= read -r -d '' source; do
name="$(basename "${source}")"
target="${AUDIOBOOK_ROOT}/${name}"

if [[ -e "${target}" || -L "${target}" ]]; then
    if [[ -L "${target}" ]]; then
        current_target="$(readlink "${target}")"

        if [[ "${current_target}" == "${source}" ]]; then
            echo "EXISTS: ${name} -> ${current_target}"
            ((existing+=1))
            continue
        fi

        echo "ERROR: Existing symlink points somewhere else:"
        echo "  ${target} -> ${current_target}"
        exit 1
    fi

    echo "SKIP: ${target} already exists and is not a symlink."
    ((existing+=1))
    continue
fi

ln -s "${source}" "${target}"

echo "LINK: ${name} -> ${source}"
((created+=1))

done < <(
find "${BOOKS_ROOT}"
-mindepth 1
-maxdepth 1
( -type d -o -type l )
-print0
| sort -z
)

echo
echo "Created: ${created}"
echo "Existing: ${existing}"
echo
echo "Audiobook compatibility links complete."