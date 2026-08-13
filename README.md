# homelab-m920

Infrastructure-as-code for the Lenovo ThinkCentre M920Q that serves as the primary Homelab server.

## Architecture

The M920Q runs Debian 13 with Docker and Tailscale.

- `/opt/homelab` — this repository and rebuildable infrastructure
- `/srv/homelab/appdata` — persistent application configuration and databases
- `/srv/homelab/media` — media libraries
- `/srv/homelab/backups` — local backups

## Principles

1. Infrastructure belongs in Git.
2. Persistent application state does not belong in Git.
3. Media does not belong in Git.
4. Services should be reproducible from this repository.
5. Secrets should never be committed.
6. The server should be recoverable from a clean Debian installation.

## Planned services

- Audiobookshelf
- Calibre-Web
- Homepage
- Monitoring
- Tailscale

See `docs/architecture.md` and `docs/storage.md` for the current design.
