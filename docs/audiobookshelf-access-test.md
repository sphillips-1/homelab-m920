# Audiobookshelf Cloudflare Access compatibility test

This test uses `audiobooks-access-test.shelfgoblin.dev`. It routes to the
existing Audiobookshelf container but has its own DNS record and Cloudflare
Access application. The production hostname, OIDC configuration, container,
database, and media are unchanged.

The test uses One-Time PIN plus the same exact-email allow-list as Calibre-Web.
It has no bypass or service-token policy. The open Audiobookshelf mobile-app
request for custom request headers means service tokens are not yet a practical
per-user mobile solution.

## Enable and deploy

1. Set GitHub environment variable `ENABLE_AUDIOBOOKSHELF_ACCESS_TEST=true`.
2. Run the protected Terraform Apply workflow. The safe plan should add exactly
   one proxied DNS record and one Access application, with no deletes or
   replacements.
3. On the M920Q after pulling the same commit, run:

   ```bash
   cd /opt/homelab
   sudo bash scripts/configure-cloudflared.sh --mode access
   sudo docker compose -f services/cloudflared/compose.yml up -d
   sudo bash scripts/verify-audiobookshelf-access-test.sh shelfgoblin.dev
   ```

The ingress route may be deployed before Terraform; without DNS it is not
publicly reachable. If Terraform is applied first, the protected test hostname
may return the tunnel's 404 fallback until cloudflared is redeployed.

## Compatibility matrix

Use a disposable or non-administrator Audiobookshelf user. Record app version,
OS version, result, and timestamps for each test.

| Client | Required checks |
| --- | --- |
| Private desktop browser | OTP, Audiobookshelf OIDC, library load, playback, seek, progress, logout |
| Android app | Add server, OTP handoff, OIDC return, covers, stream, download, offline play, progress sync, reconnect |
| iOS app | Same checks as Android |
| Browser reconnect | WebSocket reconnect after sleep and network change |
| Mobile reconnect | Wi-Fi to cellular transition, token refresh, background/resume |

Inspect Cloudflare Access audit events, `docker logs --since 15m cloudflared`,
and `docker logs --since 15m audiobookshelf` using matching timestamps.

## Decision rule

- Adopt Access on production only if every supported native client completes
  authentication, streaming, downloading, sync, and reconnect tests.
- If browsers pass but native clients fail at Cloudflare authentication, keep
  production on Authentik/OIDC and use Tailscale for private native access.
- Do not add an Access bypass or distribute a shared service token.

Both test resources use `prevent_destroy`. Cleanup therefore requires a
separate reviewed change that deliberately removes those guards and passes a
destructive-plan review.
