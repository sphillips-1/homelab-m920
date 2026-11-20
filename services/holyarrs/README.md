# HolyArrs video stack

HolyArrs manages the new movie and TV libraries. Its dedicated video
qBittorrent instance uses separate configuration and download paths from
the existing audiobook workflow. Both video services join the external
`homelab` network and share a single read-write `/data` mount.

## Rollout review

1. Use a dedicated GitHub Actions job on the M920 runner with the
   `infrastructure` environment. Run
   `bash scripts/check-m920-video-storage.sh` before applying either Compose
   project. Confirm TCP ports 6262 and 8088 are free before publishing them.
2. Set `VIDEO_LAN_IP` to the current M920 LAN address from the network
   inventory. Apply this Compose project and wait for both health checks.
   Open HolyArrs at port 6262 and video qBittorrent at port 8088 on that
   address. Set up authentication before enabling requests. Keep both
   ports off Cloudflared and router forwarding.
3. During the approved Jellyfin restart window, apply `compose.video.yml`
   alongside the existing Jellyfin Compose file with its current environment.
   The override adds two read-only library paths. A later base-only apply
   drops these mounts. The updated canonical deploy script applies the
   override whenever the video storage guard passes.
   If the video bind mount is unavailable, applying or starting Jellyfin
   with the override will fail. To recover without the new libraries,
   recreate Jellyfin with its base Compose file.
4. Configure the apps, then validate the flow below with a file you have
   permission to download and share. No VPN is enabled by this Compose
   project. A future VPN configuration should preserve HolyArrs access to
   the qBittorrent Web UI and route the downloader's peer traffic through
   the VPN namespace.

## Application settings

- **Video qBittorrent** uses `/data/downloads/complete` as its default save
  path and `/data/downloads/incomplete` for unfinished torrents. Set a
  permanent Web UI password after the temporary-password login. Keep Web UI
  authentication enabled and disable automatic router port mapping. Set
  seeding limits to suit the content and tracker. The Compose project
  publishes no BitTorrent peer port.
- **HolyArrs** uses movie and TV folders `/data/media/movies` and
  `/data/media/tv`. Connect qBittorrent at
  `http://qbittorrent-video:8088` with the configured credentials and set
  its watched category to `holyarrs`. Use `/data/downloads/complete` as an
  extra import folder. Both containers see the same paths, so remote path
  mapping is unnecessary. Enable completed-download imports and keep
  torrents available for seeding. Use the Jellyfin integration to refresh
  the libraries after imports, with Jellyfin reachable at
  `http://jellyfin:8096` and a private Jellyfin API key.
- **Jellyfin** can include `/media/video-movies` and `/media/video-tv` in
  the existing libraries. Keep the existing QSV settings and prefer direct
  playback when the client supports the media. Trigger a library scan
  after adding the paths.

For a completed test download, compare device and inode numbers for the
downloaded file and imported file with `stat -c '%d:%i %h %n'`. Both numbers
should match and the link count should be at least two. Confirm Jellyfin
recognizes the import and plays it. Force a transcode once to verify QSV,
then check the existing Audiobookshelf and Calibre-Web flows and review
container health.

Upstream references: [HolyArrs installation](https://docs.holyarrs.com/start/install/),
[storage layout](https://docs.holyarrs.com/start/folders/),
[download clients](https://docs.holyarrs.com/start/connect/),
[Jellyfin integration](https://docs.holyarrs.com/library/media-servers/),
and [LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/).
