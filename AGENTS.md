# Homelab M920Q Agent Guide

This repository manages the primary Lenovo ThinkCentre M920Q Homelab server.

## Source of truth

Treat this repository as the authoritative source for server configuration and deployment logic.

Do not assume a generic Docker Compose layout when modifying this repository. Follow the structure already established here.

## Storage boundary

Rebuildable infrastructure belongs under `/opt/homelab`.

Persistent state belongs under `/srv/homelab`.

- `/srv/homelab/appdata` — application state
- `/srv/homelab/media` — media
- `/srv/homelab/backups` — backups

Never commit application databases, media, generated metadata, credentials, or other machine-specific state.

## Change expectations

- Prefer idempotent scripts.
- Make scripts safe to run more than once where practical.
- Document architectural changes.
- Avoid hard-coding secrets.
- Preserve existing deployment conventions unless there is a documented reason to change them.
