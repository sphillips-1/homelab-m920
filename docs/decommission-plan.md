# Future identity decommission plan

This is a plan only. No Authentik, Entra, HCP workspace, DNS, or credential is
removed by the Cloudflare-first migration.

## Preconditions and rollback

- Calibre-Web passes approved-user, denied-user, logout, expiry, and origin
  tests through Cloudflare Access for an agreed observation period.
- Audiobookshelf has a separately proven native-client design, or remains on
  its current authentication path.
- At least two administrators can recover Cloudflare and HCP Terraform access.
- Current Authentik and Entra state/backups are verified.
- Roll back if approved users cannot authenticate, an unapproved identity can
  reach an origin, native clients regress, or the Access app is unavailable.

Rollback disables only the new Calibre-Web Access application/policy or reverts
its reviewed Terraform change. It does not delete tunnel, DNS, Authentik, or
Entra resources.

## Later destruction order

1. Remove application dependencies on Authentik and prove direct origin login.
2. Export final Entra and Authentik inventories and take application backups.
3. Remove the Entra credential, service principal, and application with a
   reviewed plan in `homelab-m920-entra`. Never remove state merely to hide
   live resources.
4. After the workspace has no live managed objects, archive/delete it under the
   HCP organization retention policy.
5. Remove Authentik providers/outposts, then its containers and appdata only
   after backup and rollback windows expire.
6. Remove `auth.shelfgoblin.dev` from the Cloudflare Terraform `for_each`,
   review the explicit DNS deletion, and apply it last.
7. Revoke and remove obsolete Azure/GitHub OIDC configuration, Azure
   credentials, and Authentik secrets from protected stores.

If a live resource must become unmanaged, use `terraform state rm` only after
documenting its new owner and import command. State removal is not resource
decommissioning.
