# Audiobookshelf

Audiobookshelf deployment configuration will live here.

Persistent state belongs under `/srv/homelab/appdata/audiobookshelf` and media under `/srv/homelab/media/audiobooks`.

cat > services/audiobookshelf/README.md <<'EOF'
# Audiobookshelf

Audiobookshelf deployment configuration lives here.

Persistent state:

- `/srv/homelab/appdata/audiobookshelf` → `/config`
- `/srv/homelab/appdata/audiobookshelf/metadata` → `/metadata`

Audiobook media:

- `/srv/homelab/media/audiobooks` → `/audiobooks`

Application data and media are intentionally kept outside the Git repository.
EOF