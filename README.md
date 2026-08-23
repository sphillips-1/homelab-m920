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

## Service status

Deployed and managed by this repository:

- Audiobookshelf
- Calibre-Web
- Authentik with Google OAuth identity
- Cloudflare DNS and Tunnel Terraform
- Cloudflare Tunnel
- Beszel container status and resource monitoring
- Tailscale-based private access

Planned:

- Homepage

See `docs/architecture.md` and `docs/storage.md` for the current design.
Automatic container deployment from `main`, runner setup, verification, and
rollback behavior are documented in `docs/container-deployment.md`.

Cloudflare Tunnel's safe-by-default setup is documented in
`docs/cloudflare-tunnel.md`. Authentik deployment, Google OAuth enrollment,
recovery, backup, and validation are documented in `docs/authentik.md`.
Application authorization, client compatibility, deployment, and rollback are
documented in `docs/application-sso.md`.
New-user onboarding, existing-user migration, client setup, troubleshooting,
and offboarding are documented in `docs/user-onboarding.md`.
The concluded Cloudflare Access compatibility experiment and Terraform cleanup
controls are documented in `docs/terraform-zero-trust.md`. Entra External ID is
pending decommission and is not being expanded.

## Application access

- LAN: Audiobookshelf is available at `http://<m920q-lan-ip>:13378` and
  Calibre-Web at `http://<m920q-lan-ip>:8083`.
- Tailscale: use the same ports with the M920Q's Tailscale name or IP; SSH port
  forwarding is not required for normal private browser access.
- Internet: only the Cloudflare Tunnel may route application hostnames.
  It connects to the containers over Docker's `homelab` network; no router port
  forwarding is configured or required.

Public application routes must not remain unauthenticated. Authentik is the
single application identity provider: proxy authentication protects
Calibre-Web and native OIDC protects Audiobookshelf browser/mobile clients.
Cloudflare remains the DNS, proxy, and outbound-only Tunnel edge. Tailscale
remains the preferred private path.
