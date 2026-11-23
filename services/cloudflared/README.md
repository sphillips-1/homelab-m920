# Cloudflared

This service runs the named Cloudflare Tunnel as an outbound-only Docker
connector. Its credentials and rendered configuration are deliberately stored
outside Git at `/srv/homelab/appdata/cloudflared`.

Use `sudo bash ../../scripts/configure-cloudflared.sh --mode safe` before
deploying it.
See the [tunnel guide](../../docs/cloudflare-tunnel.md) for recovery inputs,
GitHub Actions deployment, and verification.
