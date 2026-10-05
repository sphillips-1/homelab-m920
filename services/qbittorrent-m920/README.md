# M920 qBittorrent

## Dedicated torrent USB

The existing 116 GiB ext4 USB (UUID
`e440863e-34ce-4c29-b05a-c5dfda01a743`, label `AUDIOBOOKS`) mounts directly at
`/srv/homelab/media/torrents-m920`. Both complete and incomplete payloads live
on this device. Appdata remains on the M920 internal disk.

`scripts/setup-m920-torrent-storage.sh` mounts this specific existing filesystem
without formatting it, preserves existing files, and installs its UUID-based
fstab entry. It refuses conflicting mounts or pre-existing internal payloads.
Deployment verifies the UUID, ext4, writable mount and download directories.
The container entrypoint independently refuses an internal-disk download bind
or a missing USB marker, including during Docker restart or manual Compose use.
Missing USB storage therefore prevents qBittorrent startup. The rest of the
M920 can boot without this optional device. Do not remove it while downloading;
stop the Compose stack and unmount this path first.

Run `bash scripts/check-m920-torrent-storage.sh` on the host and the existing
API verifier in the qBittorrent network namespace after storage changes.

Separate from the existing Pi instance; no Pi state or downloads are migrated.
Appdata lives in `/srv/homelab/appdata/qbittorrent-m920`; downloads live in
`/srv/homelab/media/torrents-m920/{complete,incomplete}`.

Open `https://torrents.shelfgoblin.dev` or the qBittorrent tile in Authentik.
An administrator must explicitly grant `torrent-users`; ordinary invitations
do not grant torrent administration. Everyone approved shares full control of
this instance. Authentik forward authentication protects the Web UI and API.

The application listens only on container loopback and bypasses native login
only there. An Nginx sidecar shares its network namespace and checks Authentik
on every application request before proxying to loopback. No Web UI or peer
ports are published. Host/CSRF checks remain enabled. Peer connections use
normal M920 internet egress; this service does not provide a VPN.

Deployment is integrated into `scripts/deploy-services.sh`. The configurator
must run while the application is stopped because qBittorrent writes its own
configuration on shutdown. Recreate both application and gateway together.
Terraform manages the new tunnel DNS CNAME; SSO mode routes it to the gateway.
Other tunnel modes return the catch-all 404 for this hostname.

Before upgrades, stop this stack and archive appdata to
`/srv/homelab/backups/qbittorrent-m920`, then restart it. Back up payloads
separately. To revoke access, remove the user's `torrent-users` membership.
To close public access, restore tunnel safe mode.
