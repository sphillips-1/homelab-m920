# Cloudflare Tunnel foundation (pre-SSO)

## Security model

Cloudflare Tunnel is the only intended public ingress. The `cloudflared`
container makes outbound connections to Cloudflare and reaches the two web
applications on Docker's private `homelab` network. Do **not** forward router
ports 80 or 443. Do not expose SSH, Tailscale, Docker, databases, or any other
host service through this tunnel.

Audiobookshelf and Calibre-Web bind to `127.0.0.1` on the host, not
`0.0.0.0`. Tailscale remains the administration path; use SSH port forwarding
from a Tailnet device when direct private browser access is needed, for example:

```bash
ssh -N -L 13378:127.0.0.1:13378 -L 8083:127.0.0.1:8083 user@<tailscale-host>
```

The normal pre-SSO state is **safe mode**. It keeps the tunnel connected and
DNS records in place but returns HTTP 404 for `audiobooks.<DOMAIN>`,
`books.<DOMAIN>`, and `auth.<DOMAIN>`. It does not rely only on an Access
policy, so an accidental policy deletion cannot expose an application.

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
| `auth` | `<TUNNEL_UUID>.cfargotunnel.com` |

Do not create public hostnames or routes for any other internal service.

## Deploy in PRE-SSO SAFE STATE

Render the safe ingress configuration and deploy:

```bash
sudo bash ./scripts/configure-cloudflared.sh --mode safe
sudo ./scripts/deploy-services.sh
sudo bash ./scripts/verify-cloudflare-tunnel.sh safe
```

The expected external response from both application hostnames is HTTPS 404.
The `auth` hostname is intentionally reserved and also returns 404. The
router needs no port-forwarding rule.

## TEMPORARY TEST ACCESS

Before enabling test routing, create **two Cloudflare Zero Trust Access
applications**, one for `audiobooks.<DOMAIN>` and one for `books.<DOMAIN>`.
Use self-hosted application type, exact hostname paths (`/*`), and an Allow
policy restricted to your own identity/email domain. Verify in an incognito
browser that Cloudflare Access requests authentication and that anonymous
requests cannot reach either application. This is a Cloudflare Access gate,
not Authentik; Authentik is not configured by this repository yet.

Only after those policies are enabled, run:

```bash
sudo bash ./scripts/configure-cloudflared.sh --mode test
sudo docker compose -f services/cloudflared/compose.yml up -d
sudo bash ./scripts/verify-cloudflare-tunnel.sh test
```

Test mode routes `audiobooks.<DOMAIN>` to Audiobookshelf and
`books.<DOMAIN>` to Calibre-Web. `auth.<DOMAIN>` still returns 404. This is
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

Stopping it makes all three public hostnames unavailable but does not affect
the local applications or Tailscale. Keep the safe-mode configuration as the
normal ready state.

## Validation and troubleshooting

`verify-cloudflare-tunnel.sh` validates Compose syntax, container status,
loopback-only application publication, container-to-container connectivity,
tunnel connection logs, DNS resolution, and HTTPS behavior. It must be run on
the M920Q after deployment; this repository checkout cannot validate the live
Cloudflare account, DNS, or router.

- If the tunnel does not connect, inspect `docker logs cloudflared` and confirm
  the UUID and JSON credential match the Cloudflare dashboard.
- If DNS does not resolve, confirm the CNAME target is exactly
  `<TUNNEL_UUID>.cfargotunnel.com`, proxied, and in the correct zone.
- If test mode exposes an app without an Access login, immediately return to
  safe mode and correct the Access application/policy before retesting.
- If cloudflared cannot resolve an app name, confirm all three containers are
  attached to the external `homelab` Docker network.

## Future Authentik integration

The future Authentik service will join `homelab` and replace the reserved
`auth.<DOMAIN>` 404 route. Authentik/Google SSO will then become the
application authentication layer; Cloudflare Access can remain an edge gate
or be revised deliberately. Do not turn the current temporary Access policy
into an unauthenticated permanent route. Keep safe mode until that design is
implemented and tested.
