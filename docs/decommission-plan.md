# Entra and Cloudflare Access decommission plan

Authentik is now the active identity provider for both applications and is not
a decommission target. Entra remains pending decommission. The failed
Audiobookshelf Cloudflare Access experiment is removed separately with an
exact-address Terraform deletion gate.

## Preconditions and rollback

- Calibre-Web passes Authentik proxy login and authorization tests.
- Audiobookshelf passes Authentik OIDC browser and native-client tests.
- At least two administrators can recover Cloudflare and HCP Terraform access.
- Current Authentik and Entra state/backups are verified.
- Roll back if approved users cannot authenticate, an unapproved identity can
  reach an origin, native clients regress, or the Access app is unavailable.

Rollback restores the previous Terraform commit or cloudflared routing mode. It
does not delete the tunnel, production DNS, Authentik, or Entra resources.

## Later destruction order

1. Verify both applications use Authentik successfully and export final Entra
   inventory.
2. Remove the Entra credential, service principal, and application with a
   reviewed plan in `homelab-m920-entra`. Never remove state merely to hide
   live resources.
3. After the workspace has no live managed objects, archive/delete it under the
   HCP organization retention policy.
4. Revoke and remove obsolete Azure/GitHub OIDC configuration and Azure/Entra
   credentials from protected stores.

If a live resource must become unmanaged, use `terraform state rm` only after
documenting its new owner and import command. State removal is not resource
decommissioning.
