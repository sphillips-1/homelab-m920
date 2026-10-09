# Application SSO

## Active architecture

Public traffic uses Cloudflare Tunnel only; router ports 80/443 remain closed.
`audiobooks.shelfgoblin.dev` routes to Audiobookshelf, which enforces native
OIDC with Authentik. In normal `sso` mode, `books.shelfgoblin.dev` routes
through the Authentik embedded proxy before reaching Calibre-Web.
`status.shelfgoblin.dev` also routes through the embedded proxy before reaching
Beszel. Beszel additionally uses native Authentik OIDC behind that proxy, with
password login disabled and OAuth-only creation of ordinary dashboard users.
`auth.shelfgoblin.dev` continues to route to Authentik.

`torrents.shelfgoblin.dev` reaches the M920 qBittorrent gateway, which enforces
Authentik forward authentication on every Web UI/API request. Its portal tile
and application access require explicit `torrent-users` membership. Standard
invitations do not grant this group. Approved users share full instance control.
See `services/qbittorrent-m920/README.md` for storage and deployment details.

LAN and Tailscale continue to use host ports 13378 and 8083. Audiobookshelf
uses OpenID exclusively on every network path; its persisted password hashes
remain in the database for rollback but password authentication is disabled.
Calibre-Web accepts Authentik's verified email header for single sign-on and
retains its own permissions behind the proxy.

## Authorization

Authentik has separate applications and providers:

- `Audiobookshelf` / `audiobookshelf`: confidential OIDC provider, restricted
  to `audiobooks-users`.
- `Books` / `books`: proxy provider, restricted to `books-users`.
- `Status` / `status`: proxy provider, restricted to `status-users`.
- `Beszel` / `beszel`: hidden confidential OIDC application behind Status,
  restricted to `status-users` and Google-linked identities. The strict callback
  is `https://status.shelfgoblin.dev/api/oauth2-redirect`. Deployment reconciles
  both Authentik and PocketBase from repo scripts; credentials live only in their
  databases. The existing Status application remains the visible portal tile.

Google login establishes identity only. To grant access, add the existing
Authentik user to the relevant group. The normal service invitation grants all
three groups. Remove a group membership to revoke only that application.
Disable the user or remove all three memberships to revoke all application
access.

The Google source uses the dedicated `google-source-enrollment` flow. It may
create an Authentik identity after Google verifies the account, but it does not
add any application group. A new user will remain denied until an administrator
explicitly grants the relevant group membership.

Audiobookshelf auto-registration is disabled. The owner's existing root user
is matched by email, preserving its user ID, password, permissions, progress,
and history. Create and map additional Audiobookshelf users deliberately before
granting their Authentik group membership.

Follow `docs/user-onboarding.md` for new users, migration of existing users,
browser/mobile setup, troubleshooting, and offboarding.

## Audiobookshelf clients

The deployed server is 2.36.0 and uses the persisted base path
`/audiobookshelf`. Browser and mobile callbacks are therefore:

```text
https://audiobooks.shelfgoblin.dev/audiobookshelf/auth/openid/callback
https://audiobooks.shelfgoblin.dev/audiobookshelf/auth/openid/mobile-redirect
```

The official Android/iOS client uses native OIDC with PKCE and
`audiobookshelf://oauth`. Use server URL
`https://audiobooks.shelfgoblin.dev/audiobookshelf` and choose the Authentik
login. Do not put Cloudflare Access in front of this hostname: its browser-only
session does not authenticate the app's later API requests.

Lissen uses the same server URL and the **Continue with Authentik / Google**
button. Deployment runs `scripts/reconcile-audiobookshelf-clients.py` inside
the invitation provisioner, reusing its protected ABS API credential. It adds
`lissen://oauth` to ABS's `authOpenIDMobileRedirectURIs` through
`/api/auth-settings`, preserves existing callbacks, and verifies the saved list.
Repeat deployments are a no-op when Lissen is already allowed. An existing
wildcard is preserved; this script never introduces one. No Authentik provider
callback change is required. Other authentication settings are left untouched.

To reconcile an already deployed server from the canonical checkout:

```bash
sudo docker exec -i authentik-invitation-provisioner python - \
  < /opt/homelab/scripts/reconcile-audiobookshelf-clients.py
```

The setting persists in `/srv/homelab/appdata/audiobookshelf`. Reverting code
does not remove it; to revoke Lissen, remove its URI in ABS **Settings →
Authentication → Allowed Mobile Redirect URIs** after removing it from
`REQUIRED_URIS` in the reconciler. Validate sign-in and playback on the phone
after deployment.

## Calibre-Web and OPDS

Calibre-Web 0.6.27 does not support generic Authentik OIDC. Browser access uses
the embedded proxy and a dedicated `X-Calibre-Web-User` reverse-proxy login
header derived from the Authentik identity's email. Invitations
provision the required native account before access is granted.
The live instance was not initialized when this integration was prepared:
`/srv/homelab/media/ebooks` had no `metadata.db`, and the application redirected
to `/admin/dbconfig`. Do not expose OPDS until a real Calibre library and strong
native Calibre-Web credentials exist.

Interactive Authentik login is not compatible with ordinary OPDS readers.
When OPDS is needed, add a narrowly scoped tunnel rule or separate hostname
that reaches only `/opds` and uses Calibre-Web HTTP Basic credentials. Never
bypass authentication for the whole Books application.

## Deployment and validation

Before changing public routes, run `sudo scripts/backup-applications.sh` and
copy backups off-host. Render the single-provider route with:

```bash
sudo bash scripts/configure-cloudflared.sh --mode sso
sudo docker compose -f services/cloudflared/compose.yml restart cloudflared
sudo bash scripts/verify-cloudflare-tunnel.sh sso
```

Validate anonymous, authorized, unauthorized, logout/login, LAN, and Tailscale
paths. Confirm Books redirects to `auth.shelfgoblin.dev`. Check
`docker logs --tail 100 cloudflared` for ongoing origin errors.

## Recovery and rollback

Private service access remains available at ports 13378, 8083, and 9000, but
Audiobookshelf login still requires Authentik while its password method is
disabled. Keep the `akadmin` and Calibre-Web recovery credentials. If SSO
fails, render safe mode and redeploy cloudflared:

```bash
sudo bash scripts/configure-cloudflared.sh --mode safe
sudo docker compose -f services/cloudflared/compose.yml up -d
```

This closes public application origins without affecting LAN/Tailscale. To
restore application state, stop the affected container, replace its appdata
from the matching pre-SSO archive, and restart it. Restore Authentik using its
SQL dump, file archive, and the separately protected stable `.env` secret key.

The former `access` mode is retained only as migration history and must not be
used as the normal deployment mode.
