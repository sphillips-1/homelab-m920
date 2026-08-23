# Cloudflare Tunnel foundation (pre-SSO)

## Security model

Cloudflare Tunnel is the only intended public ingress. The `cloudflared`
container makes outbound connections to Cloudflare and reaches the web
applications on Docker's private `homelab` network. Do **not** forward router
ports 80 or 443. Do not expose SSH, Tailscale, Docker, databases, or any other
host service through this tunnel.

Audiobookshelf publishes `13378:80` and Calibre-Web publishes `8083:8083` on
the M920Q. They are reachable directly at
`http://<m920q-lan-ip>:13378` and `http://<m920q-lan-ip>:8083` on the LAN, and
at the same ports using the M920Q's Tailscale name or IP. SSH port forwarding
is not required for normal Tailscale browser access. These host publications do
not affect the tunnel: `cloudflared` continues to connect directly to
`audiobookshelf:80` and `calibre-web:8083` over the Docker `homelab` network.

The normal pre-SSO state is **safe mode**. It keeps the tunnel connected and
DNS records in place but returns HTTP 404 for `audiobooks.<DOMAIN>`,
`books.<DOMAIN>`, and `status.<DOMAIN>`. The identity hostname routes to Authentik. Safe mode does not
rely only on an Access policy, so an accidental policy deletion cannot expose
either content application.

The repository's current desired production mode is recorded in
`config/cloudflared/desired-mode`. Deployments render that mode before starting
the connector, so the checked-in ingress template and the live tunnel do not
drift. Change it to `safe` for a persistent emergency closure; `test` and the
deprecated `access` mode are intentionally rejected by automatic deployment.

## Prerequisites

- The domain is active in Cloudflare and Cloudflare is authoritative for DNS.
- Docker Compose is installed on the M920Q.
- No router port forwarding exists for ports 80 or 443.
- You have Cloudflare permissions to create tunnels, DNS records, and Access
  applications.

## Create the named tunnel

Run the repository-managed setup helper on the M920Q. It reuses an existing
local tunnel JSON credential when possible; otherwise it opens the interactive
Cloudflare login flow, creates a named tunnel, writes the ignored local `.env`,
renders safe mode, and deploys the connector.

```bash
sudo bash ./scripts/setup-cloudflared-tunnel.sh --domain example.com
```

Pass the real Cloudflare zone (without a protocol) instead of `example.com`.
The helper prints the tunnel UUID and writes the local environment file. To
select a local credential explicitly, use `--tunnel-id <UUID>`.

```bash
sudo cat services/cloudflared/.env
```

`services/cloudflared/.env` is ignored by Git. The required values are
`CLOUDFLARE_DOMAIN`, `CLOUDFLARE_TUNNEL_ID`, and
`CLOUDFLARE_TUNNEL_CREDENTIALS_FILE`. The credential JSON is secret. The
temporary `cert.pem` is removed by the helper after successful deployment.

In the Cloudflare DNS dashboard, create proxied CNAME records:

| Name | Target |
| --- | --- |
| `audiobooks` | `<TUNNEL_UUID>.cfargotunnel.com` |
| `books` | `<TUNNEL_UUID>.cfargotunnel.com` |
| `status` | `<TUNNEL_UUID>.cfargotunnel.com` |
| `auth` | `<TUNNEL_UUID>.cfargotunnel.com` |

Do not create public hostnames or routes for any other internal service. The
one narrow path exception is `auth.<DOMAIN>/invite/*`, which routes to the
invitation landing endpoint. That endpoint only issues a short-lived signed
handoff cookie and redirects to Authentik's Google source; the provisioning API
on the same container remains protected by an internal bearer secret.

## Deploy in PRE-SSO SAFE STATE

Render the safe ingress configuration and deploy:

```bash
sudo bash ./scripts/configure-cloudflared.sh --mode safe
sudo ./scripts/deploy-services.sh
sudo bash ./scripts/verify-cloudflare-tunnel.sh safe
```

The expected external response from all application hostnames is HTTPS 404.
The `auth` hostname routes to Authentik. The router needs no port-forwarding
rule.

## TEMPORARY TEST ACCESS

Before enabling test routing, create Cloudflare Zero Trust Access applications
for `audiobooks.<DOMAIN>`, `books.<DOMAIN>`, and `status.<DOMAIN>`.
Use self-hosted application type, exact hostname paths (`/*`), and an Allow
policy restricted to your own identity/email domain. Verify in an incognito
browser that Cloudflare Access requests authentication and that anonymous
requests cannot reach either application. This is a Cloudflare Access gate,
not Authentik. Authentik and Google OAuth are deployed as the identity layer,
but neither application is integrated with Authentik yet.

Only after those policies are enabled, run:

```bash
sudo bash ./scripts/configure-cloudflared.sh --mode test
sudo docker compose -f services/cloudflared/compose.yml up -d
sudo bash ./scripts/verify-cloudflare-tunnel.sh test
```

Test mode routes `audiobooks.<DOMAIN>` to Audiobookshelf,
`books.<DOMAIN>` to Calibre-Web, and `status.<DOMAIN>` to Beszel.
`auth.<DOMAIN>` continues to route to Authentik. This is
**TEMPORARY TEST ACCESS** and would be unauthenticated if the Access policies
are missing, disabled, or incorrectly scoped.

## Disable temporary public access immediately

Return the connector to safe mode; this is the required action after testing:

```bash
sudo bash ./scripts/configure-cloudflared.sh --mode safe
sudo docker compose -f services/cloudflared/compose.yml up -d
sudo bash ./scripts/verify-cloudflare-tunnel.sh safe
```

For an additional emergency stop, disable the tunnel in the Cloudflare
dashboard or stop the connector:

```bash
sudo docker compose -f services/cloudflared/compose.yml stop
```

Stopping it makes all four public hostnames unavailable but does not affect
the local applications or Tailscale. Keep the safe-mode configuration as the
normal ready state.

## Validation and troubleshooting

`verify-cloudflare-tunnel.sh` validates Compose syntax, container status,
LAN/Tailscale-capable application publication, container-to-container connectivity,
tunnel connection logs, DNS resolution, and HTTPS behavior. It must be run on
the M920Q after deployment; this repository checkout cannot validate the live
Cloudflare account, DNS, or router.

- If the tunnel does not connect, inspect `docker logs cloudflared` and confirm
  the UUID and JSON credential match the Cloudflare dashboard.
- If DNS does not resolve, confirm the CNAME target is exactly
  `<TUNNEL_UUID>.cfargotunnel.com`, proxied, and in the correct zone.
- If test mode exposes an app without an Access login, immediately return to
  safe mode and correct the Access application/policy before retesting.
- If cloudflared cannot resolve an app name, confirm all application containers are
  attached to the external `homelab` Docker network.

## Authentik identity route

The Authentik server joins `homelab`, and both tunnel modes route
`auth.<DOMAIN>` to `http://authentik-server:9000`. Safe mode still returns 404
for Audiobookshelf and Calibre-Web. Authentik/Google establishes the identity
layer only; it does not protect either application yet. Do not turn temporary
application test routes into unauthenticated permanent routes.
