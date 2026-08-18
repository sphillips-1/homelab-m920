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
- `inventory-authentik.ps1` records only non-user configuration identifiers for
  adoption review; its output is ignored.
- `import-authentik-blueprint.ps1` reconciles the reviewed internal blueprint
  instance with the shared HCP Terraform state and produces a plan. It never
  applies.

See `docs/terraform-adoption.md` for the required review, secret handling, and
rollback gates.
