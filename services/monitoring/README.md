# Container status

[Beszel](https://beszel.dev/) provides the private status page for the M920Q.
It shows the running state, CPU, memory, network, and storage usage for every
Docker container and keeps historical metrics and alerts.

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

## Operations

```bash
docker compose --profile agent ps
docker compose --profile agent logs --tail 100 beszel beszel-agent
```

To replace or rotate the agent credentials, run the same helper again. It
atomically replaces the protected `.env` file and recreates only the agent.
