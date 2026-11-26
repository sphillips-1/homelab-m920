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

## Prepare or restore the tunnel

Recover the existing named tunnel and credential per the [recovery guide](recovery.md).
The ignored `services/cloudflared/.env` supplies `CLOUDFLARE_DOMAIN`,
`CLOUDFLARE_TUNNEL_ID`, and `CLOUDFLARE_TUNNEL_CREDENTIALS_FILE`. Keep the
credential JSON private under `/srv/homelab/appdata/cloudflared`. The release
skips the connector until a runtime config exists. Once the credential and
environment are in place, render it with
`sudo bash scripts/configure-cloudflared.sh --mode safe`.

The legacy `setup-cloudflared-tunnel.sh` helper starts a connector itself.
Use the [runbook](deployment-runbook.md#recovery-automation-gaps) for the
first-install gap in the GitHub Actions path. Preserve the existing tunnel UUID
and Terraform-managed DNS during a recovery.

## Deploy and verify

Set the checked-in desired mode to `safe` or `sso` and deploy through
[GitHub Actions](container-deployment.md). Verify with
`sudo bash scripts/verify-cloudflare-tunnel.sh <safe|sso>`. In safe mode,
application hostnames return 404 and the identity hostname routes to Authentik.
Use SSO mode after verifying application access policies.

The temporary `test` mode is historical. It bypassed Authentik and depended
on Cloudflare Access policies for each app hostname. The production workflow
accepts only `safe` and `sso`.

For immediate emergency closure, stop the connector with
`sudo docker compose -f services/cloudflared/compose.yml stop`. This takes
public ingress offline while leaving private access available. Commit the
safe desired mode and deploy through Actions before restoring the connector.

HolyArrs routes to the Authentik embedded outpost in `sso` mode. The
outpost checks membership in `holyarrs-users` before forwarding to
HolyArrs. HolyArrs still uses its native Authentik OIDC client for the
application session. Deployment checks that anonymous requests to the
site and OIDC callback redirect to the outpost before restarting the
connector. Verify the full sign-in flow off-LAN with an approved account
and check that an account outside the group is denied.

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
