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
