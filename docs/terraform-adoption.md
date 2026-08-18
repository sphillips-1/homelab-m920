# Authentik and Cloudflare Terraform adoption

## Target state

HCP Terraform workspace `homelab-m920` is the remote state backend. GitHub
Actions plans and applies both providers from `terraform/`:

- Cloudflare provider resources own the existing production tunnel and the
  three proxied application DNS records.
- An Authentik provider resource owns one internal blueprint instance. The
  blueprint can reconcile most Authentik configuration models atomically,
  including applications, providers, groups, flows, stages, policies, sources,
  mappings, and outposts represented by the reviewed export.
- PostgreSQL, uploaded files, application users, passwords, sessions, tokens,
  event history, and write-only provider secrets remain backup/secret-store
  concerns. Terraform state is not a replacement for `backup-authentik.sh`.

The checked-in `terraform/authentik/homelab.yaml` is intentionally a no-op seed.
`AUTHENTIK_ADOPTION_READY` must remain false until it has been replaced by a
reviewed live export and the one-time state reconciliation is complete.

## One-time Authentik capture

On the M920Q, from `/opt/homelab`:

```bash
sudo scripts/backup-authentik.sh
sudo scripts/export-authentik-blueprint.sh
```

The raw export is private and ignored by Git. Authentik omits write-only values,
including OAuth client secrets. Review it outside Git, retain configuration
objects needed to rebuild the identity layer, and remove at least:

- users, credentials, tokens, invitations, sessions, and event records;
- machine-generated reports and transient tasks;
- bundled/system objects that Authentik recreates itself;
- stale applications, providers, sources, and outposts;
- any personal attributes that do not belong in source control.

Replace missing secret values with Authentik `!Env` references and provide those
environment variables to the server and worker from the ignored Authentik
`.env`. Never paste a secret into the blueprint, Terraform variables, a plan, or
GitHub variables. Save the curated result as
`terraform/authentik/homelab.yaml`.

From a trusted workstation, create a short-lived Authentik API token for an
administrator and run:

```powershell
.\scripts\inventory-authentik.ps1
.\scripts\import-authentik-blueprint.ps1
```

The inventory contains only adoption identifiers and is still ignored because
it describes the private deployment. The import script securely prompts for a
token and imports an existing `homelab-terraform` blueprint instance when
present. Otherwise, it leaves creation for a reviewed plan. It always plans
with adoption enabled and never applies.

Before the first apply, require all of the following:

1. A current off-host Authentik backup and separately protected `.env`.
2. A reviewed blueprint with no users or literal secrets.
3. The existing Cloudflare tunnel and DNS records already present in HCP state.
4. A plan with no deletes or replacements and only the expected Authentik
   blueprint creation/update.
5. A tested LAN/Tailscale recovery route and `akadmin` recovery procedure.

## Cloudflare capture and state

The existing safe adoption scripts remain authoritative:

```powershell
.\scripts\inventory-cloudflare.ps1
.\scripts\import-cloudflare-adoption.ps1
.\scripts\plan-cloudflare-adoption.ps1
```

They inventory and import the locally configured tunnel and the three production
CNAMEs. Do not import an entire zone or account blindly: zone rulesets and some
account-wide settings are authoritative collections, and incomplete HCL can
remove rules on the next apply. Add further Cloudflare resources one product at
a time, capture the complete remote object, import its ID into the same HCP
workspace, and require a zero-change plan before enabling management.

## GitHub environment

Keep the existing protected `infrastructure` environment and add:

GitHub environment secrets:

- `AUTHENTIK_TOKEN` — short-lived/scoped API token used by plans and applies;
- existing `CLOUDFLARE_API_TOKEN` and `TF_API_TOKEN`.

GitHub environment variables:

- `AUTHENTIK_URL=https://auth.shelfgoblin.dev`;
- `AUTHENTIK_ADOPTION_READY=false` until reconciliation is complete, then
  `true`;
- the existing HCP and Cloudflare identifiers documented in
  `terraform-zero-trust.md`.

PR validation does not contact Authentik. Same-repository PR plans and manual
applies use protected credentials. Both workflows reject every delete and
replacement. Apply remains manual through `workflow_dispatch`.

After deployment, verify Authentik login twice, Google enrollment, both
application authorization groups, Audiobookshelf browser/mobile OIDC,
Calibre-Web proxy login, anonymous denial, and the private recovery route. Then
require a second plan with no changes.
