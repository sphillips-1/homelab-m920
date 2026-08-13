# `create-directories.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Create the persistent Homelab directory structure.
#
# Intended location:
#   /opt/homelab/scripts/create-directories.sh
#
# Persistent data lives outside the Git repository:
#   /srv/homelab
#
# Safe to run multiple times.

HOMELAB_ROOT="/srv/homelab"

APPDATA_ROOT="${HOMELAB_ROOT}/appdata"
MEDIA_ROOT="${HOMELAB_ROOT}/media"
BACKUP_ROOT="${HOMELAB_ROOT}/backups"

echo "Creating Homelab directories..."

# Application state
mkdir -p \
    "${APPDATA_ROOT}/audiobookshelf" \
    "${APPDATA_ROOT}/calibre-web" \
    "${APPDATA_ROOT}/homepage" \
    "${APPDATA_ROOT}/monitoring"

# Media
mkdir -p \
    "${MEDIA_ROOT}/audiobooks" \
    "${MEDIA_ROOT}/ebooks"

# Backups
mkdir -p \
    "${BACKUP_ROOT}/appdata" \
    "${BACKUP_ROOT}/database"

# Set ownership to root by default.
# Individual services can be given more specific ownership later
# when their container UID/GID requirements are known.
chown -R root:root "${HOMELAB_ROOT}"

# Directories should be accessible to root and readable/traversable
# by other users, without making application data world-writable.
find "${HOMELAB_ROOT}" -type d -exec chmod 755 {} \;

echo
echo "Homelab directory structure created:"
echo
echo "${HOMELAB_ROOT}/"
echo "├── appdata/"
echo "│   ├── audiobookshelf/"
echo "│   ├── calibre-web/"
echo "│   ├── homepage/"
echo "│   └── monitoring/"
echo "├── media/"
echo "│   ├── audiobooks/"
echo "│   └── ebooks/"
echo "└── backups/"
echo "    ├── appdata/"
echo "    └── database/"
echo
echo "Done."
```
