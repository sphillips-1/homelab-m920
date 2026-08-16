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
- Authentik
- Tailscale

See `docs/architecture.md` and `docs/storage.md` for the current design.

Cloudflare Tunnel's pre-SSO, safe-by-default setup is documented in
`docs/cloudflare-tunnel.md`.

## Application access

- LAN: Audiobookshelf is available at `http://<m920q-lan-ip>:13378` and
  Calibre-Web at `http://<m920q-lan-ip>:8083`.
- Tailscale: use the same ports with the M920Q's Tailscale name or IP; SSH port
  forwarding is not required for normal private browser access.
- Internet: only the Cloudflare Tunnel may route the two application hostnames.
  It connects to the containers over Docker's `homelab` network; no router port
  forwarding is configured or required.

Public application routes must not remain unauthenticated. They stay in the
safe 404 state until deliberately integrated with Authentik. Authentik itself
is routed at `https://auth.shelfgoblin.dev`; application SSO is intentionally
not part of the identity-layer deployment.
