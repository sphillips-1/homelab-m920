# Clean Debian recovery

Use this guide to recover the M920Q on clean Debian 13. Git provides the
infrastructure. An existing installation also requires backups, private inputs,
storage, and access to external accounts.

## Keep a recovery set off the server

| Item | Preserve |
| --- | --- |
| Release | Last verified Git SHA, enabled services, and image digests for mutable tags. The release command pulls images again. |
| Appdata | Consistent database and file backups, including accounts, settings, qBittorrent resume state, importer queues, monitoring, and optional service state. |
| Media | Separate library and download backups as needed. Preserve the Calibre library with its `metadata.db`, the mount layout, and disk UUIDs. |
| Secrets | Encrypted copies of protected service environment files, tunnel credential JSON, API and OIDC keys, and other private inputs for enabled services. Keep decryption access independent of the host. |
| External configuration | Access to the GitHub `infrastructure` environment, HCP Terraform workspace and state, Cloudflare, Google OAuth, Tailscale, and the Pi-hole/router settings. |

The backup helpers cover Authentik (PostgreSQL dump and files), Audiobookshelf
and Calibre-Web (appdata and the ebook library), Jellyfin (appdata), and
Readest (database dump, storage and PostgreSQL configuration). These are
targeted backups. Verify off-host copies separately and document coverage for
the remaining services and media. Treat database dumps and archives as sensitive.

## Restore in order

1. Prepare Debian and the runner using the [deployment runbook](deployment-runbook.md).
   Restore the LAN reservation and Pi-hole DNS using the [network inventory](network-inventory.md).
2. Reattach media and torrent disks and restore the mount definitions by UUID.
   Verify the backing filesystem for each path before restoring files. See
   [storage](storage.md) for the canonical paths.
3. Restore appdata and media with application writers stopped. Preserve numeric
   owners, modes, and symlinks. Restore cold database snapshots with compatible
   database versions. For logical backups, initialize a compatible private
   database and restore with the matching tool (`psql` for Authentik SQL,
   `pg_restore` for the Readest custom archive). Pair each dump with its matching
   files and secrets, and verify the restored database before enabling writers.
4. Restore protected runtime files and GitHub environment settings. Preserve
   the existing Terraform workspace and tunnel identity. Keep application
   ingress closed until identity and SSO work. The pipeline re-renders the
   committed Cloudflare mode, so use a reviewed `safe` desired mode for a staged
   recovery with ingress enabled.
5. Dispatch **Deploy** from GitHub Actions with `main` selected. The current
   workflow runs Terraform before deployment. If its Authentik provider needs
   the failed server online first, the normal workflow is blocked. See the
   [staging gap](deployment-runbook.md#recovery-automation-gaps).
6. Confirm the deployed SHA, readiness, account access and permissions, real
   library playback, download and import paths, and monitoring. Verify Jellyfin
   Quick Sync and expected LAN, Tailscale, and public SSO exposure before
   restoring normal public routes through GitHub Actions.

Record the backup timestamp, commit, and results of a clean Debian restore
drill. Release rollback reapplies Compose definitions. Restore persistent state
separately when an incompatible database migration requires it.
