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
- `configure-cloudflared.sh --mode sso` enables final native-OIDC/proxy
  application routing after providers and policies have been configured.
