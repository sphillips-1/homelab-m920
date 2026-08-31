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

## First-time setup

The normal deployment starts the dashboard first and leaves the agent disabled
until its credentials exist.

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
