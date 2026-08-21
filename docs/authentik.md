# Authentik identity layer

## Architecture and scope

This deployment establishes Google -> Authentik identity and application SSO.
Audiobookshelf uses native OIDC; Calibre-Web uses the Authentik proxy's verified
email header with a pre-provisioned local account for application permissions.

```text
Cloudflare Tunnel -> homelab -> authentik-server:9000
                                  |
                       authentik-internal
                         |             |
                  authentik-worker  PostgreSQL 16
```

The deployment pins Authentik `2026.5.6`. This version's supported Compose
architecture uses PostgreSQL, server, and worker; Redis is no longer required.
PostgreSQL and the worker publish no ports. The server publishes port 9000 for
LAN/Tailscale recovery only. Never forward it on the router.

Persistent state is under `/srv/homelab/appdata/authentik`:

- `postgresql` - database, including users, flows, policies, and source config
- `data` - icons, backgrounds, uploads, and reports
- `certs` - filesystem certificates, if used
- `custom-templates` - optional UI templates

## Secrets and deployment

Create the ignored local environment on the M920Q:

```bash
cd /opt/homelab
sudo install -m 0600 services/authentik/.env.example services/authentik/.env
openssl rand -base64 36 | tr -d '\n'  # PG_PASS
openssl rand -base64 60 | tr -d '\n'  # AUTHENTIK_SECRET_KEY
sudoedit services/authentik/.env
git check-ignore services/authentik/.env
```

Paste each generated value into its matching variable. Required secrets are
`PG_PASS` and `AUTHENTIK_SECRET_KEY`. Google Client ID and Client Secret are
entered later and stored encrypted in PostgreSQL; keep both out of Git too.

```bash
sudo ./scripts/create-directories.sh
sudo docker compose -f services/authentik/compose.yml config -q
sudo docker compose -f services/authentik/compose.yml pull
sudo docker compose -f services/authentik/compose.yml up -d
sudo bash ./scripts/configure-cloudflared.sh --mode safe
sudo docker compose -f services/cloudflared/compose.yml up -d
```

From LAN or Tailscale, open
`http://192.168.4.37:9000/if/flow/initial-setup/` and set a unique strong
`akadmin` password. This is preferred to a default/bootstrap password. If an
automated first boot is necessary, use Authentik's `hash_password` command and
the optional variables in `.env.example`; remove them after the first
successful boot because Authentik only consumes them during initial setup.

## Google Cloud Console

1. Create or select a Google Cloud project and configure Google Auth Platform's
   OAuth consent screen. Choose **Internal** only for an applicable Workspace
   organization; otherwise choose **External** and initially leave it in
   Testing. Set app name `Authentik`, support/developer emails, and authorized
   domain `shelfgoblin.dev`. Basic `openid`, `email`, and `profile` scopes are
   sufficient. Add only your Google address as a test user.
2. Create credentials -> OAuth client ID -> **Web application**.
3. Authorized JavaScript origins are not required for this server-side flow.
   If Google requires one, enter only `https://auth.shelfgoblin.dev`.
4. Add exactly this Authorized redirect URI, including the trailing slash:

   `https://auth.shelfgoblin.dev/source/oauth/callback/google/`

5. Save the Client ID and Client Secret in a password manager.

## Authentik Google source and enrollment

In Admin, open **Directory -> Federation and Social login -> New Source**,
select **Google OAuth Source**, and configure:

- Name: `Google`
- Slug: `google` (it must match the callback path)
- Consumer key/secret: the Google Client ID and Client Secret
- Scopes: the source defaults (`openid email profile`)
- Authentication flow: `default-source-authentication`
- Enrollment flow: `google-source-enrollment`

The dedicated enrollment flow uses the standard username prompt, user-write,
and login stages. It intentionally omits the shared
`default-source-enrollment-if-sso` binding so browser and mobile OIDC enrollment
both work. Google verifies identity, but this flow must not add
`audiobooks-users` or `books-users`. Application access remains an explicit
administrator decision.

Finally, edit the `default-authentication-identification` stage and add Google
under **Source settings -> Sources**. Enable **Show sources' labels** so the
login option is clearly identified. A successful first login creates only an
Authentik identity; it grants no Audiobookshelf or Calibre-Web authorization.
Follow `docs/user-onboarding.md` for approval and application-account
procedures.

## Validation

Run these on the M920Q:

```bash
sudo docker compose -f services/authentik/compose.yml config -q
docker ps --filter name=authentik
docker network inspect homelab
docker run --rm --network homelab curlimages/curl:latest -fsS http://authentik-server:9000/-/health/ready/
docker logs cloudflared --tail 100
curl -fsS https://auth.shelfgoblin.dev/-/health/ready/
sudo bash ./scripts/verify-cloudflare-tunnel.sh safe
curl -fsS http://192.168.4.37:13378/ >/dev/null
curl -fsS http://192.168.4.37:8083/ >/dev/null
```

Confirm `authentik-server` and cloudflared both belong to `homelab`; recent
cloudflared logs must show registered connections without repeated origin
errors. Repeat the two application checks through the M920Q's Tailscale name or
IP. In an incognito browser, open Authentik, choose Google, complete login,
and confirm the user reaches `/if/user/` without a redirect loop. Log out and
log in again. Confirm a newly enrolled identity receives no application groups
and cannot enter either application before administrator approval. Browser
Google SSO and Tailscale checks
require the operator's sessions and cannot be completed from a repository-only
checkout.

## Recovery

- Google is broken or an account is locked out: from LAN/Tailscale run
  `cd /opt/homelab/services/authentik && sudo docker compose run --rm server create_recovery_key 10 akadmin`.
  Open the printed one-time URL within ten minutes.
- Reset `akadmin`: `sudo docker compose exec server ak changepassword akadmin`.
- Cloudflare or DNS is down: use `http://<LAN-IP>:9000` or
  `http://<TAILSCALE-IP>:9000`.
- Service failure: inspect `docker compose ps` and logs for server, worker, and
  PostgreSQL, then test the local readiness URL.

Recovery links grant direct access; never share or persist them.

## Backup and restore

`sudo bash ./scripts/backup-authentik.sh` creates a PostgreSQL logical dump and an
archive of `data`, `certs`, and `custom-templates` in a mode-0700 timestamped
directory under `/srv/homelab/backups/authentik`. Copy it to encrypted off-host
storage. Back up `services/authentik/.env` separately in an encrypted secret
store: the stable secret key is needed to decrypt protected database values.

Restore into matching Authentik/PostgreSQL versions: stop server and worker,
restore the file archive, start PostgreSQL, pipe the SQL dump into `psql`, then
start the stack and validate. Never commit backups or secrets.

## Application-integration prerequisites

Google login/logout must pass twice, enrollment must create no application
group memberships, and the recovery path must be tested. An off-host backup
must exist, and LAN/Tailscale plus tunnel checks must pass. Do not treat
authentication to Authentik as blanket authorization to either application.
