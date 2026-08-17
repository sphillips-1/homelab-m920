# Entra External ID — pending decommission

This Terraform root is intentionally dormant. It retains the existing `Shelf
Goblin` External ID resources in HCP workspace `homelab-m920-entra` so they
remain recoverable while Cloudflare-native Access is validated. Do not apply
feature changes, rotate its OAuth credential, add permissions, or merge this
state with `homelab-m920`.

The retained resources are the `Cloudflare Access - homelab-m920` application,
its service principal, and its client credential. The tenant and GitHub Actions
bootstrap identity remain untouched. Use refresh-only plans for audits.

Destruction is a future, separately reviewed operation governed by
`../../docs/decommission-plan.md`.
