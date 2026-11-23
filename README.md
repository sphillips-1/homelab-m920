# homelab-m920

Infrastructure-as-code for the Lenovo ThinkCentre M920Q that serves as the primary Homelab server.

## Architecture

The M920Q runs Debian 13 with Docker and Tailscale.

- `/opt/homelab` — this repository and rebuildable infrastructure
- `/srv/homelab/appdata` — persistent application configuration and databases
- `/srv/homelab/media` — media libraries
- `/srv/homelab/video-data` — SSD-backed downloads and movie and TV libraries for the HolyArrs stack
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
- Jellyfin (LAN-only, with Intel Quick Sync transcoding)
- HolyArrs and a dedicated video qBittorrent instance (LAN-only, deployed from `main` when the video SSD passes preflight)
- Authentik with Google OAuth identity
- Cloudflare DNS and Tunnel Terraform
- Cloudflare Tunnel
- Beszel container status and resource monitoring
- Tailscale-based private access
- Curiosity Club kids intranet: offline games, drawing, and Vikidia at
  `http://kids.home.arpa/` (see `services/kids/README.md`)

Planned:

- Homepage

See `docs/architecture.md` and `docs/storage.md` for the current design.
Known LAN addresses are maintained in [the network inventory](docs/network-inventory.md).
See the [deployment runbook](docs/deployment-runbook.md) for Debian host setup
and first-install gaps, [recovery](docs/recovery.md) for off-host backups and
restore order, and the [service catalog](services/README.md) for application setup.
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
  Calibre-Web at `http://<m920q-lan-ip>:8083`. Jellyfin is intentionally
  LAN-only at `http://192.168.4.27:8096` and binds only to the LAN address.
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

## HolyArrs video stack

- Open [HolyArrs](https://holyarrs.shelfgoblin.dev/) on the homelab LAN or choose **HolyArrs** in the [Authentik portal](https://auth.shelfgoblin.dev/). The tile reuses an existing HolyArrs session or starts native OIDC sign-in. First sign-in can enroll members of the `holyarrs-users` Authentik group. The LAN HTTPS proxy handles the OIDC callback. The base Compose service binds port `6262` to the LAN, and the dedicated [video qBittorrent Web UI](http://192.168.4.27:8088/) uses its own login. Both services stay off the Cloudflare Tunnel and router port forwarding. See the [network inventory](docs/network-inventory.md) for the M920Q address.
- HolyArrs talks to `http://qbittorrent-video:8088` on the Docker `homelab` network and watches the `holyarrs` category. Both containers mount the same SSD-backed directory at `/data`. Video qBittorrent saves to `/data/downloads/complete` and `/data/downloads/incomplete`. HolyArrs imports completed downloads into `/data/media/movies` and `/data/media/tv`, where it can hardlink files so the originals remain available for seeding. Video qBittorrent has separate configuration and download paths from the audiobook downloader.
- HolyArrs can request a Jellyfin library refresh through `http://jellyfin:8096` using a private API key. The Jellyfin override in `main` adds read-only mounts at `/media/video-movies` and `/media/video-tv`. The `codex/m920-video-library-cutover` workflow consolidates the existing libraries and the separate approval-based video importer on the same SSD folders, with Jellyfin reading them at `/media/movies` and `/media/tv`. The cutover checks that existing library files are present as hardlinks before switching the mounts and restores the previous mounts if the switch fails.
- GitHub Actions runs the storage preflight before applying the video stack. If the SSD check fails, the deployment in `main` uses Jellyfin's base library mounts and skips applying the HolyArrs stack. LAN HTTPS, the Authentik tile, and group enrollment are configured in the branch-specific workflows on `codex/holyarrs-sso` and `codex/holyarrs-authentik-tile`. Keep the SSO Compose override in the deployment path when reapplying the stack with HTTPS and OIDC enabled. See the [HolyArrs service guide](services/holyarrs/README.md) for application settings and import verification.
