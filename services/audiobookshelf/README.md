# Audiobookshelf

Audiobookshelf deployment configuration lives here.

Persistent state:

- `/srv/homelab/appdata/audiobookshelf` → `/config`
- `/srv/homelab/appdata/audiobookshelf/metadata` → `/metadata`

Audiobook media:

- `/srv/homelab/media/audiobooks` → `/audiobooks`

Application data and media are intentionally kept outside the Git repository.

## Access

The web UI is available at `http://<m920q-lan-ip>:13378` on the LAN or
`http://<m920q-tailscale-name-or-ip>:13378` over Tailscale; SSH port forwarding
is not required. Cloudflare Tunnel reaches this container directly over the
Docker `homelab` network when an intentionally protected public route is
enabled. No router port forwarding is required, and the application must not
remain permanently exposed to the Internet without a proven authentication
path. Do not place browser-based Cloudflare Access in front of this hostname
until native-client API and WebSocket compatibility is demonstrated; use
Tailscale for private mobile access meanwhile.
