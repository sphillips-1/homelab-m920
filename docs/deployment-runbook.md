# Zero-to-production deployment runbook

This runbook describes what the repository installs and deploys on a clean
Debian 13 M920Q, the order in which an operator must run one-time scripts, and
the application setup that remains manual. It is grouped by service after the
host-wide execution order.

The automation is intentionally split into two layers:

- `scripts/bootstrap.sh` prepares the host. It does **not** deploy containers.
- `scripts/deploy-services.sh` creates shared storage and networking, then
  deploys and reconciles the container services.

Commands assume the canonical checkout is `/opt/homelab`. Persistent state and
secrets remain outside Git under `/srv/homelab` or in ignored service `.env`
files.

## End-to-end execution order

### 1. Prepare the physical host and Debian

Before running repository automation:

1. Install Debian 13 and enable the Intel integrated GPU in firmware.
2. Give the host a stable LAN address. Jellyfin binds directly to that address.
3. Confirm `/dev/dri/renderD*` exists after boot.
4. Do not configure router port forwarding for ports 80, 443, 9000, or any
   application port.

Optional hostname configuration, if Debian was not already installed with the
desired name:

```bash
sudo bash ./scripts/configure-hostname.sh m920q
```

This changes the system hostname and the `127.0.1.1` entry in `/etc/hosts`.

### 2. Bootstrap the host

From a temporary clone or downloaded copy of the repository, run:

```bash
sudo bash ./scripts/bootstrap.sh
```

The bootstrap performs the following work, in order:

1. verifies that the host is Debian and the script is running as root;
2. installs `ca-certificates`, `curl`, `git`, `gnupg`, and `sudo`;
3. clones or fast-forwards `main` into `/opt/homelab`;
4. invokes `scripts/install-dependencies.sh` automatically;
5. installs the common administration and GPU tools;
6. configures Docker's Debian package repository;
7. installs Docker Engine, containerd, Buildx, and the Compose plugin;
8. enables and starts Docker;
9. installs Tailscale when absent; and
10. enables and starts `tailscaled`.

Do not run `install-dependencies.sh` separately during a normal clean build; it
is part of `bootstrap.sh`. After bootstrap, authenticate the host to the
intended tailnet using the normal `tailscale up` enrollment process.

### 3. Prepare or restore persistent storage

For a new host, directory creation is automatic during deployment. It may be
run early when data must be restored before containers start:

```bash
cd /opt/homelab
sudo ./scripts/create-directories.sh
```

It creates application data, cache, media, monitoring, and backup directories
under `/srv/homelab`. `deploy-services.sh` invokes it again safely.

For a recovery, restore `/srv/homelab` after creating the directory skeleton
and before deploying services. For a host that still uses the repository's
legacy audiobook-only external mount layout, run the guarded migration once:

```bash
sudo bash ./scripts/migrate-media-storage.sh
```

Do not run the migration on a clean installation or on an already migrated
host. See `storage.md` for its preconditions and mount layout.

### 4. Create Authentik secrets

The first full deployment requires both ignored Authentik environment files.
Create the primary file before running `deploy-services.sh`:

```bash
cd /opt/homelab
sudo install -m 0600 services/authentik/.env.example services/authentik/.env
sudo editor services/authentik/.env
```

Replace every required placeholder. Generate a PostgreSQL password and
Authentik secret key, and supply the stable Audiobookshelf OIDC, Google OAuth,
and enrollment policy values. Never commit this file.

Create `services/authentik/.env.invitation` from its example with protected
placeholder values for the initial deployment:

```bash
sudo install -m 0600 services/authentik/.env.invitation.example \
  services/authentik/.env.invitation
sudo editor services/authentik/.env.invitation
```

The Audiobookshelf API token cannot be obtained until Audiobookshelf has an
administrator. Replace the placeholder later with
`install-invitation-env.sh`, as described under Authentik and invitations.

### 5. Run the first container deployment

```bash
cd /opt/homelab
sudo ./scripts/deploy-services.sh
```

The script performs the following work in this exact order:

1. creates the `/srv/homelab` directory tree;
2. creates Audiobookshelf compatibility links;
3. creates the external Docker network named `homelab`;
4. deploys Authentik PostgreSQL, server, worker, and invitation provisioner;
5. restarts the invitation provisioner to load checked-out Python changes;
6. reconciles the Authentik invite tile, status access, and Terraform CI
   permissions through `ak shell`;
7. deploys Audiobookshelf;
8. deploys Calibre-Web;
9. detects Jellyfin's LAN IP, render device, and render-device GID;
10. deploys Jellyfin and reconciles Quick Sync as its acceleration type;
11. when the protected Jellyfin Intro Skipper API-key file exists, registers,
    installs, and reconciles Intro Skipper and its Media Segment settings;
12. skips Homepage because it currently has no Compose definition;
13. deploys the Beszel dashboard, and deploys its agent only if
    `services/monitoring/.env` exists; and
14. deploys cloudflared only if its rendered runtime configuration already
    exists.

The following scripts are invoked by deployment and must not be added as
separate normal manual steps:

- `create-directories.sh`
- `create-audiobook-links.sh`
- `configure-jellyfin-host.sh`
- `configure-jellyfin-transcoding.sh`
- `configure-jellyfin-intro-skipper.sh` when its protected API-key file exists
- `reconcile-invite-creator.py`
- `reconcile-status-sso.py`
- `reconcile-authentik-ci-permissions.py`
- `reconcile-authentik-branding.py`

The Authentik deployment also installs the repository-owned bookshelf theme.
It mounts the SVG into the server and exposes the CSS to the worker, then
reconciles Authentik's supported Brand CSS and default-background fields. No
theme upload or Admin UI change is required on a clean installation. Follow
the targeted server/worker recreation in `authentik.md` when only theme file
contents change.

### 6. Complete each service's one-time setup

Complete the service sections below in this order:

1. Authentik initial administrator and Google OAuth setup
2. Audiobookshelf administrator, library, and OIDC setup
3. Authentik invitation secret installation
4. Calibre library and Calibre-Web initial setup
5. Calibre-Web SSO configuration
6. Jellyfin wizard, libraries, and GPU verification
7. Jellyfin Intro Skipper API key, reconciliation, and initial off-hours scan
8. Beszel administrator and agent pairing
9. Cloudflare Tunnel creation in safe mode
10. Terraform adoption or provisioning of Cloudflare DNS and Authentik resources
11. SSO-mode cutover and end-to-end verification

### 7. Verify the complete deployment

After all mandatory service setup is complete:

```bash
cd /opt/homelab
sudo bash ./scripts/verify-services.sh
sudo bash ./scripts/verify-jellyfin-gpu.sh
sudo bash ./scripts/verify-cloudflare-tunnel.sh sso
curl -fsS https://auth.shelfgoblin.dev/if/flow/default-authentication-flow/ \
  | grep -F "Shelf Goblin Authentik theme"
curl -fsS https://auth.shelfgoblin.dev/static/dist/assets/images/bookshelf-background.svg \
  | grep -F "Bookshelves in a quiet private library"
```

`verify-services.sh` checks the expected containers and local HTTP endpoints.
The two service-specific scripts validate Quick Sync and the public tunnel/SSO
routes respectively.

### 8. Enable automatic deployments

After installing and registering the existing self-hosted GitHub Actions runner
with the `self-hosted`, `linux`, `x64`, and `m920` labels, run once:

```bash
sudo bash ./scripts/install-container-deployment.sh RUNNER_USER
```

This installs `/usr/local/sbin/homelab-deploy` and a restricted sudo rule. A
push to `main` that changes services, scripts, or container workflows then runs
`deploy-release.sh` through the runner. The release process locks deployment,
backs up affected state, validates and pulls images, deploys services, verifies
readiness, records the deployed SHA, and reapplies the previous Compose version
on failure.

## Services

### Host foundation: Docker and Tailscale

**Automated deployment**

- `bootstrap.sh` installs the initial packages and repository.
- Its child `install-dependencies.sh` installs Docker Engine, Compose, GPU
  utilities, and Tailscale, then enables Docker and `tailscaled`.

**Manual work**

1. Optionally run `configure-hostname.sh` before service deployment.
2. Enroll the host with Tailscale after bootstrap.
3. Confirm Docker, Compose, Tailscale, and `/dev/dri/renderD*` are available.

### Shared storage and Docker network

**Automated deployment**

- `deploy-services.sh` runs `create-directories.sh` and
  `create-audiobook-links.sh` on every deployment.
- It creates the external `homelab` Docker network if absent.
- Rebuildable files stay under `/opt/homelab`; persistent data stays under
  `/srv/homelab`.

**Manual work**

- Run `create-directories.sh` separately only when restoring data before the
  first deployment.
- Run `migrate-media-storage.sh` only for the documented legacy storage
  conversion.

### Authentik and invitation provisioner

**Automated deployment**

Compose deploys PostgreSQL 16, Authentik server and worker, and the private
invitation provisioner. Deployment also reconciles the invite creator,
`status-users` access, and the narrowly scoped Terraform service-account
permissions. The server receives the bookshelf stylesheet and background as
read-only mounts from the checked-out repository, making the login design part
of both clean installs and ordinary deployments.

Persistent state is stored under `/srv/homelab/appdata/authentik`. Authentik is
available privately on host port 9000 for recovery and over the `homelab`
network for Cloudflare Tunnel. Port 9000 must never be forwarded by the router.

**Manual work, in order**

1. Create and populate `services/authentik/.env` and
   `services/authentik/.env.invitation` before the first deployment.
2. Open the private port 9000 URL and complete the Authentik initial setup.
3. Configure the Google Cloud OAuth client, Authentik Google source, enrollment
   rules, groups, providers, applications, and outpost as documented in
   `authentik.md` and `application-sso.md`, unless these are being reconciled
   from the adopted Terraform blueprint.
4. After the Audiobookshelf root user exists, replace the temporary invitation
   values by running:

   ```bash
   sudo rm /opt/homelab/services/authentik/.env.invitation
   sudo bash /opt/homelab/scripts/install-invitation-env.sh
   sudo ./scripts/deploy-services.sh
   ```

   The installer extracts the Audiobookshelf root API token, generates the
   internal provisioner token, and writes a mode-0600 ignored file. The removal
   is necessary only when replacing the deliberately created first-deploy
   placeholder file; the installer refuses to overwrite an existing file.

5. Use `create-service-invitation.sh NAME` later for each invitation; it is an
   operational action, not part of host bootstrap. The shell wrapper invokes
   `create-service-invitation.py`; do not run the Python child directly.

### Audiobookshelf

**Automated deployment**

- Deploys `ghcr.io/advplyr/audiobookshelf:2.36.0`.
- Publishes host port 13378 for LAN and Tailscale access.
- Mounts configuration, audiobook media, and metadata from `/srv/homelab`.
- Makes the service reachable to Cloudflare Tunnel on the private Docker
  network.

**Manual work, in order**

1. Open port 13378 and create the root administrator.
2. Add the audiobook library using the container path `/audiobooks/Books`.
3. Configure the Authentik OIDC client/provider values described in
   `application-sso.md`.
4. Run `install-invitation-env.sh` as described above.
5. Test browser login and native mobile clients before considering the service
   complete.

### Calibre-Web

**Automated deployment**

- Deploys `lscr.io/linuxserver/calibre-web:latest` on host port 8083.
- Mounts application state at `/config` and the canonical ebook library at
  `/books`.

**Manual work, in order**

1. Restore or copy a valid Calibre library, including `metadata.db`, to
   `/srv/homelab/media/ebooks`.
2. Open port 8083, set the library path to `/books`, change the initial
   `admin` / `admin123` password immediately, and finish application setup.
3. Stop the container, configure SSO, and start it again:

   ```bash
   sudo docker stop calibre-web
   sudo python3 /opt/homelab/scripts/configure-calibre-sso.py
   sudo docker start calibre-web
   ```

4. Verify Authentik browser SSO and retain local application users for Calibre
   permissions and OPDS compatibility.

### Jellyfin

**Automated deployment**

- `configure-jellyfin-host.sh` writes the ignored Compose environment using the
  detected LAN address, Intel render device, and owning group ID.
- Compose deploys `jellyfin/jellyfin:10.11.11`, binds port 8096 only to the LAN
  address, mounts movies and TV read-only, and exposes the GPU device.
- `configure-jellyfin-transcoding.sh` changes the persisted acceleration type
  to QSV and preserves a one-time pre-QSV backup.
- When `services/jellyfin/.intro-skipper.env` exists, deployment uses supported
  Jellyfin APIs to register and install Intro Skipper and reconcile conservative
  Intro, Recap, Outro, and Media Segment settings. It never patches Jellyfin Web.
- Jellyfin is never routed through Cloudflare and is not exposed over
  Tailscale by this repository.

**Manual work, in order**

1. If automatic LAN detection chooses the wrong interface, run
   `configure-jellyfin-host.sh` with `JELLYFIN_LAN_IP` before redeploying.
2. Open the LAN URL, create the administrator, and add Movies at
   `/media/movies` and Shows at `/media/tv`.
3. Confirm Intel QuickSync in the transcoding settings and do not enable AV1.
4. Run `verify-jellyfin-gpu.sh`.
5. Force one real transcode and confirm QSV/VA-API log entries and Intel video
   engine activity.
6. In **Dashboard -> API Keys**, create a dedicated administrator key for
   repository reconciliation, then install it without committing the secret:

   ```bash
   sudo install -m 0600 services/jellyfin/.intro-skipper.env.example \
     services/jellyfin/.intro-skipper.env
   sudo editor services/jellyfin/.intro-skipper.env
   sudo bash /opt/homelab/scripts/configure-jellyfin-intro-skipper.sh
   ```

   The reconciler verifies Jellyfin and Jellyfin FFmpeg/Chromaprint compatibility
   before making changes. Preserve the ignored key file in the encrypted secret
   backup used for other service `.env` files.
7. During an off-hours window, start the initial analysis:

   ```bash
   sudo bash /opt/homelab/scripts/run-jellyfin-intro-scan.sh
   ```

   The first scan is CPU intensive; later analysis is incremental and uses the
   persisted fingerprint cache. Confirm generated segments and client playback
   actions with the exact commands in `services/jellyfin/README.md`, or run:

   ```bash
   sudo bash /opt/homelab/scripts/verify-jellyfin-intro-skipper.sh EPISODE_ID
   ```

### Beszel monitoring

**Automated deployment**

- The first deployment starts the Beszel dashboard on host port 8090.
- When `services/monitoring/.env` exists, subsequent deployment enables the
  agent profile. The agent reads the Docker socket read-only and communicates
  with the dashboard over a Unix socket.

**Manual work, in order**

1. Open port 8090 and create the first administrator.
2. Add a Docker system named `m920q` in Beszel.
3. Install the generated key and token interactively:

   ```bash
   sudo bash /opt/homelab/scripts/configure-beszel-agent.sh
   ```

   The helper writes the protected ignored `.env` and recreates only the agent.

4. Confirm container discovery and the `Homelab Media` filesystem chart.

### Cloudflare Tunnel and DNS

**Automated deployment**

- Cloudflared is deliberately skipped until runtime credentials and a rendered
  configuration exist.
- Once configured, normal deployment renders the checked-in desired mode
  (`safe` or `sso`) and deploys cloudflared last.
- Terraform manages the named tunnel record and the four public DNS records for
  `auth`, `audiobooks`, `books`, and `status` after adoption is enabled.

**Manual work, in order**

1. Create or reuse the named tunnel and deploy it in safe mode:

   ```bash
   sudo bash ./scripts/setup-cloudflared-tunnel.sh --domain example.com
   ```

   The helper calls `create-directories.sh`, performs interactive Cloudflare
   login when necessary, creates the ignored `.env`, renders safe mode, starts
   cloudflared, and attempts safe-mode verification.

2. Create or adopt the proxied DNS records. When adopting existing Cloudflare
   resources into Terraform, follow the ordered adoption scripts below instead
   of recreating resources.
3. Keep application routes in safe mode until Authentik and application SSO are
   tested.
4. Before the production cutover, back up application state and enable SSO:

   ```bash
   sudo bash ./scripts/backup-applications.sh
   sudo bash ./scripts/configure-cloudflared.sh --mode sso
   sudo docker compose -f services/cloudflared/compose.yml restart cloudflared
   sudo bash ./scripts/verify-cloudflare-tunnel.sh sso
   ```

5. For an emergency closure, render `safe` mode and recreate cloudflared.
   `test` mode is temporary and must be protected by Cloudflare Access first;
   `access` mode is retained only as deprecated migration history.

### Terraform-managed Cloudflare and Authentik configuration

The normal GitHub workflow validates, plans, rejects destructive changes, and
applies Terraform after the one-time adoption gates are enabled. These scripts
are not part of a clean container bootstrap; use them only when adopting the
existing production configuration.

**One-time Authentik adoption order**

1. `backup-authentik.sh`
2. `export-authentik-blueprint.sh`
3. `sanitize-authentik-blueprint.py`
4. `export-authentik-adoption-env.py` through the exact private redirection
   procedure in `terraform-adoption.md`
5. `install-authentik-adoption-env.sh`
6. `inventory-authentik.ps1`
7. `import-authentik-blueprint.ps1`
8. `create-authentik-adoption-token.py` only if a temporary local adoption
   token is required
9. `revoke-authentik-adoption-token.py` immediately after that token is no
   longer needed
10. `create-authentik-ci-token.py` when provisioning the dedicated CI identity

`apply-authentik-blueprint.sh` is a CI post-apply gate and should not normally
be run manually. The three `reconcile-*.py` scripts are deployment internals
and should also not be run directly.

**One-time Cloudflare adoption order**

1. `inventory-cloudflare.ps1`
2. `import-cloudflare-adoption.ps1`
3. `plan-cloudflare-adoption.ps1`

Review every inventory and plan before enabling the production Terraform apply
workflow. The adoption scripts import existing objects; they are not a
replacement for `setup-cloudflared-tunnel.sh` on a brand-new installation.

### Homepage

Homepage is planned only. The service directory contains documentation but no
Compose file, so `deploy-services.sh` skips it and installs no Homepage
container.

## Manual script index

This index lists operator-invoked scripts in lifecycle order. Conditional and
maintenance commands should be run only when their stated condition applies.

| Order | Script | When to run |
| --- | --- | --- |
| 1 | `configure-hostname.sh` | Optional, before bootstrap/service deployment if the hostname must change. |
| 2 | `bootstrap.sh` | Once on a clean Debian host; it calls `install-dependencies.sh`. |
| 3 | `create-directories.sh` | Optional before a restore; otherwise automatic. |
| 4 | `migrate-media-storage.sh` | Conditional one-time legacy storage migration only. |
| 5 | `deploy-services.sh` | First deployment after secrets exist; safe to rerun. |
| 6 | `install-invitation-env.sh` | Once after the Audiobookshelf root user exists. |
| 7 | `configure-calibre-sso.py` | Once after Calibre-Web and Authentik are configured; rerun for mapped existing users. |
| 8 | `verify-jellyfin-gpu.sh` | After Jellyfin setup and after relevant GPU/image changes. |
| 9 | `configure-jellyfin-intro-skipper.sh` | Once after creating its protected Jellyfin API key; later deployments reconcile it automatically. |
| 10 | `run-jellyfin-intro-scan.sh` | Once during an off-hours window for the existing library; safe to rerun. |
| 11 | `verify-jellyfin-intro-skipper.sh` | After installation and with an optional episode ID to verify generated segments. |
| 12 | `configure-beszel-agent.sh` | Once after creating the Beszel system; rerun to rotate credentials. |
| 13 | `setup-cloudflared-tunnel.sh` | Once after applications and Authentik exist; safe to rerun. |
| 14 | Terraform adoption scripts | Only for adoption, in the service-specific order above. |
| 15 | `backup-applications.sh` | Before application SSO/public route changes and during maintenance. |
| 16 | `configure-cloudflared.sh` | For explicit safe/test/SSO route transitions; normal deploys render the desired checked-in mode. |
| 17 | `verify-cloudflare-tunnel.sh` | Immediately after each tunnel mode change. |
| 18 | `verify-services.sh` | After full deployment or for manual health validation. |
| 19 | `install-container-deployment.sh` | Once after the self-hosted GitHub runner exists. |
| 20 | `create-service-invitation.sh` | Operationally, once for each new invitation. |
| 21 | `backup-authentik.sh` | Before Authentik changes and as part of backup operations. |
| 22 | `backup-jellyfin.sh` | Before Jellyfin changes and as part of backup operations. |
| 23 | `remove-legacy-untracked-pull-blockers.sh` | Only when the documented legacy untracked files prevent a Git pull. |

`deploy-release.sh` is invoked by the installed CI entry point, not directly by
an operator during normal operation. `install-dependencies.sh`,
`create-audiobook-links.sh`, `configure-jellyfin-host.sh`,
`configure-jellyfin-transcoding.sh`, `apply-authentik-blueprint.sh`, and the
`reconcile-*.py` scripts are child/internal automation in the normal path.

## Completion criteria

The build is complete when:

- Docker and Tailscale are running;
- the protected Authentik environment files exist and contain no placeholders;
- Authentik PostgreSQL, server, worker, and invitation provisioner are healthy;
- Audiobookshelf, Calibre-Web, Jellyfin, Beszel, the Beszel agent, and
  cloudflared are healthy;
- Audiobookshelf and Calibre-Web work privately and through their intended SSO
  paths;
- Jellyfin works only on the LAN and completes a verified QSV transcode;
- Intro Skipper is active, its analysis task completes, at least one TV episode
  has Intro/Recap/Outro Media Segments, and a supported client exposes the
  configured skip actions;
- Beszel discovers the containers and media filesystem;
- the public application routes require Authentik while the identity route is
  healthy;
- `verify-services.sh`, `verify-jellyfin-gpu.sh`, and
  `verify-cloudflare-tunnel.sh sso` pass; and
- the self-hosted runner can deploy an exact commit from `origin/main` through
  `/usr/local/sbin/homelab-deploy`.
