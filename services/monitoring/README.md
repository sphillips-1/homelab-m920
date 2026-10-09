# Container status

[Beszel](https://beszel.dev/) provides the private status page for the M920Q.
It shows the running state, CPU, memory, network, and storage usage for every
Docker container and keeps historical metrics and alerts.

The Authentik-protected Status hostname also exposes an Audiobookshelf
listening leaderboard:

```text
https://status.shelfgoblin.dev/top-users/
```

The leaderboard route requires Authentik even though the Beszel root remains
available privately on port 8090. It ranks Audiobookshelf users by their actual
hours listened during the previous seven days. Authentik also presents a
**Top listeners** application tile to members of `status-users`, so the page is
available directly from the Authentik library without navigating through
Beszel.

The dashboard is available on the LAN and Tailscale at:

```text
http://<m920q-address>:8090
```

Public access is available at `https://status.shelfgoblin.dev` through the
Cloudflare Tunnel and Authentik proxy. Membership in the Authentik
`status-users` group is required. Beszel account data and metrics persist under
`/srv/homelab/appdata/monitoring`.

## Native Authentik SSO

The Status proxy controls public access and protects the leaderboard. Beszel also
uses a separate confidential OIDC provider, so clicking **Authentik** on its login
page reuses the same Authentik session. Dashboard password login is disabled on
every network path. Use the canonical HTTPS hostname for OIDC; LAN/Tailscale port
8090 remains a private recovery endpoint, but its IP address is not an allowed
OAuth callback. PocketBase superuser recovery at `/_/` retains password login.

Every deployment runs `scripts/configure-beszel-sso.py`. It reconciles the hidden
Beszel application/provider in Authentik, restricting access to `status-users`
and identities linked to Google, then updates only the Beszel users collection’s
OAuth options through the supported PocketBase API. It verifies the saved settings
and advertised authentication methods. The existing Status and Top listeners tiles,
proxy routing, user IDs, roles, system assignments, and metrics are preserved.

Approved first-time OAuth users are created as ordinary Beszel users; existing
users match by verified Google email. New users see only systems explicitly shared
with them. SSO grants no administrator role or automatic access to every system.
The initial administrator must already exist and use its exact Google email.

Provider credentials are generated once by Authentik and reused on every deployment.
The helper captures them in memory, takes a consistent SQLite backup under
`/srv/homelab/backups/beszel-sso`, creates a randomly named temporary PocketBase
superuser, configures Beszel, and deletes that superuser in a finally block (also
on API failures). Credentials, tokens, databases, and backups are never committed.
Do not run the Authentik reconciler directly: its captured output contains the
client secret. A killed process or failed Docker cleanup requires removing its
`sso-deploy-*` superuser through the private PocketBase recovery UI before retrying.

To reconcile an existing deployment from the canonical checkout:

```bash
sudo python3 /opt/homelab/scripts/configure-beszel-sso.py
```

For recovery, use the existing PocketBase superuser through LAN/Tailscale `/_/`.
To re-enable dashboard password login temporarily, change
`DISABLE_PASSWORD_AUTH` to `"false"` in the Compose source and recreate Beszel;
changing the PocketBase checkbox alone will be overwritten at restart. A code
rollback restores the old Compose environment but leaves persisted OAuth settings;
restore the pre-change database backup with Beszel stopped only if necessary.

After deployment, verify in a fresh browser: an approved existing owner can sign
in with Authentik and sees the same systems and admin role; another approved user
can sign in and sees only shared systems; a user outside `status-users` is denied.
Check `/top-users/` still works and that password login is unavailable. Automated
configuration verification does not substitute for this browser round trip.

References: [Beszel OAuth](https://beszel.dev/guide/oauth) and
[Authentik integration](https://integrations.goauthentik.io/monitoring/beszel/).

## First-time setup

The normal deployment starts the dashboard first and leaves the agent disabled
until its credentials exist. Create the first Beszel administrator using its exact
verified Google email before native SSO reconciliation; a deployment without an
existing administrator stops with a clear setup error. Complete the first-user
setup on the private dashboard, then rerun deployment.

1. Open the dashboard and create the first admin account.
2. Choose **Add system**, name it `m920q`, and select the Docker setup.
3. Install the generated `KEY` and `TOKEN` with the interactive helper:

   ```bash
   sudo bash /opt/homelab/scripts/configure-beszel-agent.sh
   ```

   The helper hides the token while it is entered, writes the ignored `.env`
   file with mode `0600`, and recreates the agent. Do not commit `.env`.

The deployment script detects `.env`, enables the local agent, and Beszel then
discovers all containers through the read-only Docker socket. No agent port is
published: the hub and agent communicate over a local Unix socket.

The hub and agent define Docker health checks. Audiobookshelf, Calibre-Web, and
cloudflared also have service-specific checks, so Beszel can display their
health as `healthy` or `unhealthy` instead of leaving the value blank.
Jellyfin likewise reports Docker health from `/health`. Beszel automatically
records its running state, restart count, CPU, memory, and network use. The
agent's read-only `Homelab Media` mount at `/srv/homelab/storage/.beszel`
reports capacity, free space, and utilization for the external media filesystem.

## Top-users setup

The leaderboard is deployed automatically. A missing or rejected credential
shows an explanatory warning rather than stale data.

1. Create an Audiobookshelf admin API token.
2. Copy `top-users.env.example` to the ignored `.top-users.env`, then add
   `AUDIOBOOKSHELF_API_TOKEN`. Prefix the token with `Bearer `.
3. Use `TOP_USERS_ALIASES` to replace local usernames with preferred display
   names where needed.
4. Redeploy monitoring and open `/top-users/`.

Credentials and generated user activity remain under `/srv/homelab` or the
ignored `.top-users.env`; none belongs in Git.

## Operations

```bash
docker compose --profile agent ps
docker compose --profile agent logs --tail 100 beszel beszel-agent status-gateway top-users
```

To replace or rotate the agent credentials, run the same helper again. It
atomically replaces the protected `.env` file and recreates only the agent.
