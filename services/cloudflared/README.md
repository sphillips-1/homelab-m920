# Cloudflared

This service runs the named Cloudflare Tunnel as an outbound-only Docker
connector. Its credentials and rendered configuration are deliberately stored
outside Git at `/srv/homelab/appdata/cloudflared`.

Use `sudo bash ../../scripts/configure-cloudflared.sh --mode safe` before
deploying it.
See `../../docs/cloudflare-tunnel.md` for the complete setup and test process.
