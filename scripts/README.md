# Scripts

Scripts automate host setup, deployment, verification, and maintenance.

Scripts should be:

- idempotent where practical
- safe to rerun
- explicit about failures
- documented when they have destructive behavior

## Cloudflare Tunnel

Run `sudo bash scripts/setup-cloudflared-tunnel.sh --domain example.com` after
bootstrap to create or reuse a local tunnel credential, deploy the connector in
PRE-SSO SAFE mode, and write the ignored local environment file. It is safe to
rerun after repository configuration changes. It never enables application
routing; use the documented, explicit test-mode process only after Cloudflare
Access policies are in place.

## Application SSO

- `backup-applications.sh` creates consistent Audiobookshelf and Calibre-Web
  appdata/library archives under `/srv/homelab/backups/applications`.
- `backup-authentik.sh` creates an Authentik PostgreSQL dump and file archive.
- `backup-jellyfin.sh` archives Jellyfin application state while excluding
  media and disposable transcode cache.
- `remove-legacy-untracked-pull-blockers.sh` removes only the four known legacy
  untracked files that block adoption of their Git-managed replacements. It
  refuses to remove tracked files or paths with an unexpected Git status.
- `configure-cloudflared.sh --mode sso` is the normal single-provider route:
  Authentik OIDC for Audiobookshelf and the Authentik proxy for Calibre-Web.
- `configure-cloudflared.sh --mode access` is deprecated migration history.
- `configure-cloudflared.sh --mode sso` restores the Authentik proxy rollback
  application routing after providers and policies have been configured.
## Terraform adoption helpers

- `inventory-cloudflare.ps1`, `import-cloudflare-adoption.ps1`, and
  `plan-cloudflare-adoption.ps1` capture and reconcile the existing Cloudflare
  tunnel and application DNS state.
- `export-authentik-blueprint.sh` creates a private global Authentik export on
  the M920Q. The raw file is ignored and must be sanitized before use.
- `sanitize-authentik-blueprint.py` removes identity/state objects and replaces
  the stable OAuth/OIDC secrets with `!Env` references. Review its output before
  committing or planning.
- `export-authentik-adoption-env.py` runs only through `ak shell` and emits the
  four referenced live values as Docker Compose dotenv assignments. Redirect it
  to a mode-0600 ignored file; never print or commit its output.
- `install-authentik-adoption-env.sh` performs the one-time, fail-closed merge
  into the protected Authentik `.env`, keeps a mode-0600 pre-adoption backup,
  recreates server/worker, and verifies only variable presence.
- `inventory-authentik.ps1` records only non-user configuration identifiers for
  adoption review; its output is ignored.
- `import-authentik-blueprint.ps1` reconciles the reviewed internal blueprint
  instance with the shared HCP Terraform state and produces a plan. It never
  applies.
- `apply-authentik-blueprint.sh` is the production CI post-apply gate. It
  explicitly applies the Terraform-managed Authentik blueprint and waits for a
  fresh successful reconciliation result.
- `reconcile-invite-creator.py` runs through `ak shell` during service
  deployment to idempotently maintain the admin-only invite-generator tile
  while full blueprint content reconciliation is compatibility-guarded.
- `reconcile-authentik-ci-permissions.py` runs through `ak shell` during service
  deployment to keep the Terraform service account limited to the blueprint,
  flow-binding, and identification-stage permissions used by managed resources.
- `reconcile-status-sso.py` runs through `ak shell` during service deployment
  to idempotently add the `status-users` grant without submitting the full
  blueprint through Authentik's incompatible update validator.

## Container deployment

- `deploy-release.sh` is installed as the root-owned CI entry point. It deploys
  only an exact commit contained in `origin/main`, performs targeted backups,
  validates and pulls images, and rolls Compose definitions back on failure.
- `verify-services.sh` waits for expected containers and checks the local HTTP
  readiness endpoints.
- `install-container-deployment.sh RUNNER_USER` installs the entry point and a
  narrowly scoped sudoers rule for the existing GitHub Actions runner.
- `configure-beszel-agent.sh` interactively installs or rotates the local
  Beszel agent key and token without placing the token in shell history, then
  recreates only the monitoring agent.
- `configure-jellyfin-host.sh` detects the LAN address, render device, and its
  owning group ID and atomically writes Jellyfin's ignored Compose environment.
- `configure-jellyfin-transcoding.sh` idempotently reconciles Jellyfin's
  persistent playback configuration to use Intel Quick Sync, preserving a
  one-time pre-QSV backup and restarting the container only when needed.
- `verify-jellyfin-gpu.sh` validates device permissions, VA-API discovery, and
  QSV initialization inside the running container.
- `migrate-media-storage.sh` performs the guarded one-time conversion from the
  legacy audiobook-only external mount to a canonical external storage mount
  with stable audiobook, movie, and TV bind mounts.

See `docs/container-deployment.md` for runner setup, deployment behavior, and
rollback limitations.

See `docs/terraform-adoption.md` for the required review, secret handling, and
rollback gates.
