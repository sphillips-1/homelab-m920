# Deployment runbook

Production services deploy through the GitHub Actions **Deploy** workflow on
`main`. Use the [recovery checklist](recovery.md) when rebuilding the existing
installation. Use the [service catalog](../services/README.md) for app-specific
setup and verification.

## Prepare Debian and the runner

1. Install Debian 13 and enable the Intel GPU in firmware. Confirm
   `/dev/dri/renderD*` exists. Use the [network inventory](network-inventory.md)
   for the hostname and LAN address. Keep router port forwarding disabled.
2. From a temporary checkout, run `sudo bash scripts/bootstrap.sh`. Bootstrap
   prepares `/opt/homelab`, Docker, Compose, Tailscale, and host utilities.
   Enroll the machine in the intended tailnet. Use the pipeline for subsequent
   release updates to the canonical checkout.
3. Mount the required disks, verify the sources by UUID, and use
   `sudo bash scripts/create-directories.sh` from `/opt/homelab` if you need
   the directory skeleton before restore. See [storage](storage.md).
4. Register a self-hosted runner labeled `self-hosted`, `linux`, `x64`, and
   `m920`. Install the restricted entry point from `/opt/homelab` with
   `sudo bash scripts/install-container-deployment.sh RUNNER_USER`. See
   [container deployment](container-deployment.md).

## Prepare deployment inputs

- Restore appdata and original secrets before deployment. Create new secrets
  from the service examples only when provisioning new state. Authentik
  requires both `services/authentik/.env` and `.env.invitation`. When deploying
  Readest, prepare its environment before release validation, which runs
  before its normal setup helper. For Cloudflare, restore the protected
  environment, tunnel JSON, and rendered config if restoring ingress.
- Restore the GitHub `infrastructure` environment, HCP Terraform workspace,
  Cloudflare IDs and token, and Authentik URL, token and adoption settings
  as applicable. See [Terraform adoption](terraform-adoption.md).
- Verify the desired mode in `config/cloudflared/desired-mode`, active service
  prerequisites, and optional service inputs. A service can have required
  Compose inputs even when it is conditionally started.

## Deploy and verify

Push reviewed changes to `main` or select **Actions → Deploy → Run workflow →
main**. The workflow validates, applies Terraform, and invokes the host
release entry point. That entry point validates Compose, pulls images,
deploys services, reconciles settings, and checks readiness.

Use `scripts/verify-services.sh` for local readiness,
`scripts/verify-jellyfin-gpu.sh` for Quick Sync, and
`scripts/verify-cloudflare-tunnel.sh <safe|sso>` for ingress when configured.
Complete the application checks in the [recovery checklist](recovery.md).
Pair accounts and enter protected credentials using the service guides.

## Recovery automation gaps

The current pipeline expects the Terraform adoption gate to be set and can
require a reachable Authentik API before the host deployment job. Service
reconciliation also assumes existing state in places such as Beszel's owner
account. The torrent and audiobook checks expect specific disk UUIDs, so
substitute disks require reviewed configuration changes. A first-ever
installation with empty appdata has no verified path through these dependencies.
HolyArrs and the Jellyfin video overlay are already in the release path
and require the video storage preflight to pass.

Keep the existing bootstrap and release entry points. Add a read-only recovery
preflight for mounts, permissions, runtime inputs, and external dependencies.
Add a staged Actions workflow that brings up the minimum private stack for
restore or first-time configuration before running the normal production
Terraform and release gates. Add service-aware restore tooling with validated
backups and explicit restore targets, then test the procedure on clean Debian.
