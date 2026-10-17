# Readest trial

Readest runs alongside Calibre-Web at `https://readest.shelfgoblin.dev`.
The Authentik library has a **Readest** tile restricted to `readest-users`.
Import a downloaded ebook into Readest to try its reader. It does not mount,
modify, or automatically browse the canonical Calibre library.

## Architecture

Cloudflare Tunnel routes the hostname through Authentik's embedded proxy to
`readest-gateway:8080`. Only the gateway joins `homelab`; the database, GoTrue,
PostgREST, Kong, client, session adapter, and object storage share a separate
Compose network. No Readest service publishes a host port.

The official client uses Supabase sessions rather than generic OIDC. `/sso`
exchanges Authentik's verified email header for a native GoTrue session using
its admin magic-link API, consuming the one-use token server-side. Readest's
existing `/auth/callback` accepts the resulting user tokens in the URL fragment.
The gateway disables access logging and blocks browser access to signup,
admin APIs, and alternative login endpoints. Authentik is the sole public gate.
As with Calibre-Web, trusted containers on `homelab` must not forge identity
headers; neither the gateway nor its session adapter is a public ingress.

Access requires both `readest-users` and the private `.env` email allowlist.
Native accounts are separate; progress, books, and annotations belong to each
user. Ordinary media invitations do not grant Readest access. Revocation means
removing the Authentik group, removing the private allowlist entry, recreating
the `sso` service, and disabling the native account/revoking its sessions.

Official MinIO images referenced by upstream returned registry authorization
errors on 2026-10-17. A pinned official RustFS image supplies its S3-compatible
API instead; `minio` remains the private DNS alias for upstream compatibility.
Its console is disabled. `setup-storage.py` creates only the private bucket.

## Deployment and access

`scripts/deploy-services.sh` creates secrets once, starts the stack, applies
idempotent migrations, and reconciles Authentik. The client and RustFS images
are pinned by digest. Review upstream changes and back up before upgrading.

For an explicit access grant:

1. Add the verified email to `READEST_ALLOWED_EMAILS` in the mode-0600
   `/opt/homelab/services/readest/.env` and recreate `sso`.
2. Run `docker exec readest-sso python /app/provision-users.py EMAIL`.
3. Run `scripts/grant-readest-access.py` via `authentik-worker ak shell` with
   `READEST_ALLOWED_EMAILS` set to the approved emails, then rerun
   `scripts/reconcile-readest-sso.py` to invalidate portal caches.

Setup generates strong database, signing, and S3 credentials locally. Never
commit `.env`. Signup is disabled; account provisioning precedes group grants.
The hostname is declared in `terraform/main.tf` and the SSO tunnel template.
Safe, test, and legacy Access tunnel modes leave Readest unrouted.

## State, backup, and rollback

All persistent state is under `/srv/homelab/appdata/readest`: PostgreSQL data,
the image's seeded PostgreSQL custom configuration, and S3 objects (`minio`).
Secrets remain under `/opt/homelab/services/readest/.env`, following existing
service conventions; include that file in an encrypted private backup.

Run `scripts/backup-readest.sh` as root for a consistent PostgreSQL dump plus
object and configuration archives under `/srv/homelab/backups/readest`.
The existing application backup helper invokes it when Readest is running.
Restore the dump into the matching image/schema with writers stopped, restore
the S3 archive and private environment, then start and verify the stack.

To end the trial, stop its Compose project, remove its DNS/tunnel route and
Authentik application/provider/group, and preserve `/srv/homelab/appdata/readest`
until its contents are no longer needed. Calibre-Web requires no rollback.

## Upstream source

The `upstream/volumes` SQL, migration runner, and Kong configuration come from
[readest/readest](https://github.com/readest/readest) commit
`e625ab6f31f43bf3c1e6125114e1daddd048fa0e`. Their license is included.
Only line endings were normalized. See the official Docker README for image
and migration updates. This trial targets the browser; stock native clients
are not configured to use this private backend.
