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
3. Copy `.env.example` to `.env` in this directory and replace `KEY` and
   `TOKEN` with the values Beszel generated. Do not commit `.env`.
4. Run `sudo bash /opt/homelab/scripts/deploy-services.sh` again.

The deployment script detects `.env`, enables the local agent, and Beszel then
discovers all containers through the read-only Docker socket. No agent port is
published: the hub and agent communicate over a local Unix socket.

## Operations

```bash
docker compose --profile agent ps
docker compose --profile agent logs --tail 100 beszel beszel-agent
```

To rotate the agent credentials, replace the values in the ignored `.env` file
and rerun the deployment script.
