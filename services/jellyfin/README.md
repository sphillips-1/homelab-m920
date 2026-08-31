# Jellyfin

Jellyfin provides movie and TV streaming from the M920Q using the official,
version-pinned image. **Jellyfin is intentionally LAN-only.**

## Access and storage

- LAN URL: `http://192.168.4.37:8096` (or the detected LAN address in `.env`)
- Application state: `/srv/homelab/appdata/jellyfin` -> `/config`
- Transcode cache: `/srv/homelab/cache/jellyfin` -> `/cache`
- Movies: `/srv/homelab/media/movies` -> `/media/movies` (read-only)
- TV: `/srv/homelab/media/tv` -> `/media/tv` (read-only)
- Compose project: `/opt/homelab/services/jellyfin`

Movies and TV are bind-mounted from the external filesystem at
`/srv/homelab/storage`; the stable `/srv/homelab/media/...` paths keep the
Compose model independent of the physical disk mount.

Port 8096 binds only to the host's default-route LAN IPv4 address. Jellyfin is
not published through Cloudflare, protected by Cloudflare Access, exposed by
router port forwarding, or exposed via Tailscale. It is not intended for
Internet access. For a host with multiple LAN uplinks, select the address with:

```bash
sudo env JELLYFIN_LAN_IP=192.168.4.37 bash /opt/homelab/scripts/configure-jellyfin-host.sh
```

Normal deployment preserves a still-valid selected LAN address and regenerates
the render-device values. No numeric GPU group ID is committed.

## Deployment and operations

```bash
cd /opt/homelab
sudo ./scripts/deploy-services.sh

docker compose -f services/jellyfin/compose.yml ps
docker compose -f services/jellyfin/compose.yml stop
docker compose -f services/jellyfin/compose.yml start
docker compose -f services/jellyfin/compose.yml restart
docker compose -f services/jellyfin/compose.yml logs --tail 100 -f jellyfin
```

## One-time application setup

Open the LAN URL and complete Jellyfin's wizard. Create the administrator and
add Movies at `/media/movies` and Shows at `/media/tv`. Under **Dashboard ->
Playback -> Transcoding**, select **Intel QuickSync (QSV)** and the render
device reported by the host configurator. UHD 630 supports hardware decoding
for H.264, HEVC/HEVC 10-bit, MPEG-2, VC-1, VP8, and VP9/VP9 10-bit, plus H.264
and HEVC hardware encoding. Do not enable AV1. Leave low-power encoding off
unless separately validated because it can require extra firmware or kernel
configuration on Coffee Lake.

The administrator, libraries, playback selections, users, metadata, and API
keys remain application state in `/config` and are intentionally not committed.
The deployment reconciles the hardware-acceleration type to QSV with
`scripts/configure-jellyfin-transcoding.sh`; the generated `encoding.xml` still
remains persistent application state and is never committed.

## Intel Quick Sync verification

The official image includes Jellyfin FFmpeg, Intel media drivers, VA-API, and
the QSV runtime. The host configurator detects `/dev/dri/renderD*`, records its
actual owning GID in the ignored `.env`, and adds that supplemental group to the
container. After deployment run:

```bash
sudo bash /opt/homelab/scripts/verify-jellyfin-gpu.sh
```

This verifies the device on both sides of the container boundary, read/write
permission, VA-API codec discovery, and QSV initialization. Device presence
alone is not treated as proof of working transcoding.

For an end-to-end test, play a high-bitrate item and lower client quality enough
to force conversion. **Dashboard -> Active Devices** must say `Transcoding`.
While it plays, run:

```bash
sudo intel_gpu_top
docker logs --since 5m jellyfin 2>&1 | grep -Ei 'qsv|vaapi|transcod'
find /srv/homelab/appdata/jellyfin/log -type f -name 'FFmpeg.Transcode*' -mmin -10 -print
```

The FFmpeg log should contain QSV/VA-API initialization and `h264_qsv` or
`hevc_qsv`; `intel_gpu_top` should show Video engine activity. Together these
confirm hardware rather than CPU transcoding.

## Monitoring

The Compose health check polls `/health` inside the container. The normal
verification script also polls the LAN endpoint. Beszel discovers Jellyfin
through its read-only Docker socket and records running state, health, restarts,
CPU, memory, and network use. Its `Homelab Media` filesystem mount exposes
capacity, free space, and utilization for the media filesystem.

The repository does not run Prometheus, so `/metrics` is not enabled and no
second monitoring stack was introduced. Troubleshoot with:

```bash
docker inspect --format '{{.State.Status}} {{.State.Health.Status}} {{.RestartCount}}' jellyfin
curl --fail "http://$(sed -n 's/^JELLYFIN_LAN_IP=//p' services/jellyfin/.env):8096/health"
docker compose -f services/monitoring/compose.yml --profile agent logs --tail 100 beszel-agent
df -h /srv/homelab/media
```

## Intro Skipper and Media Segments

[Intro Skipper](https://github.com/intro-skipper/intro-skipper) compares episode
audio and inspects chapters/frames to detect Intro, Recap, and Outro ranges. It
writes those ranges as Jellyfin Media Segments; compatible clients consume the
server-provided segments and display their own Skip Intro or Skip Credits
action. No Jellyfin Web replacement or patch is installed.

The pinned `jellyfin/jellyfin:10.11.11` image is compatible with the current
plugin (Jellyfin 10.11.8 or newer) and contains Jellyfin FFmpeg 7.1.1-7 or newer
with Chromaprint. The reconciler verifies those facts before changing Jellyfin.
It registers `https://intro-skipper.org/manifest.json`, installs the compatible
catalog release, and configures Intro, Credits, and Recap detection. Preview and
Commercial detection are off. Fingerprint caching is on, Media Segment updates
are on, and analysis uses one below-normal-priority worker so the i5-8500T
remains available for playback. Normal Jellyfin transcoding is not CPU-limited.

Create a dedicated administrator API key in **Dashboard -> API Keys**, then:

```bash
cd /opt/homelab
sudo install -m 0600 services/jellyfin/.intro-skipper.env.example \
  services/jellyfin/.intro-skipper.env
sudo editor services/jellyfin/.intro-skipper.env
sudo bash ./scripts/configure-jellyfin-intro-skipper.sh
```

The populated file is ignored by Git and must be kept in the encrypted/off-host
secret backup used for other service `.env` files. The plugin binaries,
configuration, fingerprints, and segment-related Jellyfin state live beneath
the existing `/config` mount at `/srv/homelab/appdata/jellyfin`; therefore
`backup-jellyfin.sh` already covers them and container recreation does not
remove them. Subsequent normal deployments reconcile the desired state only
when the protected key file exists and do not reinstall an active plugin or
duplicate its repository entry.

Run the initial scan during an off-hours window:

```bash
sudo bash /opt/homelab/scripts/run-jellyfin-intro-scan.sh
```

The helper refuses to run unless Jellyfin is healthy and does not start a
duplicate task. The first full-library run is CPU- and disk-intensive and may
take hours; later analysis is incremental because newly added media is queued
automatically and fingerprints are cached. In **Dashboard -> Scheduled Tasks**,
schedule **Detect and Analyze Media Segments** daily or weekly during quiet
hours if the automatic new-item analysis is insufficient. The repository does
not overwrite a schedule you may already have chosen.

To confirm output, open Intro Skipper settings and use **Edit Timestamps &
Fingerprints**, or obtain an episode ID from its Jellyfin Web URL and query:

```bash
set -a; source /opt/homelab/services/jellyfin/.intro-skipper.env; set +a
curl --fail -H "X-Emby-Token: ${JELLYFIN_API_KEY}" \
  "http://$(sed -n 's/^JELLYFIN_LAN_IP=//p' /opt/homelab/services/jellyfin/.env):8096/MediaSegments/EPISODE_ID"
```

Enable the desired actions for Intro, Recap, and Outro under each compatible
client's playback settings. Client support varies; segment creation alone
cannot add a button to an older client.

### Intro Skipper troubleshooting

- **Plugin not appearing:** rerun the reconciler, hard-refresh the catalog, and
  confirm the manifest URL is enabled under **Plugins -> Repositories**.
- **Plugin/version incompatibility:** do not force-install a release. Confirm
  Jellyfin is at least 10.11.8 and inspect `docker logs jellyfin` for
  `NotSupported`; the version-aware manifest selects the compatible release.
- **Incorrect detection:** edit the affected timestamps in the plugin UI and
  keep conservative defaults. Exclude unusual series rather than globally
  increasing detection sensitivity.
- **No skip button:** confirm segments exist, enable segment actions in that
  client, update the client, and test with Jellyfin Web. Legacy web patches are
  neither required nor supported here.
- **Scan incomplete:** inspect **Dashboard -> Scheduled Tasks**, free space in
  `/srv/homelab/appdata/jellyfin`, and logs containing `IntroSkipper`,
  `Media Segment`, `fingerprint`, or `ffmpeg`.
- **Unsupported client:** use a current client that implements Jellyfin Media
  Segment actions; the server cannot supply client UI behavior.
- **FFmpeg/Chromaprint:** run the checks below. An immediate task failure often
  means Jellyfin cannot find its FFmpeg build or that `--enable-chromaprint` is
  absent.

### Intro Skipper verification

Run on the M920Q after deployment (replace `EPISODE_ID`):

```bash
# One-command summary (health, plugin, task, and optional episode segments)
sudo bash /opt/homelab/scripts/verify-jellyfin-intro-skipper.sh EPISODE_ID

# A: health, uptime, and restart count
docker inspect --format '{{.State.Status}} {{.State.Health.Status}} restarts={{.RestartCount}} started={{.State.StartedAt}}' jellyfin

# B: server version
docker exec jellyfin /jellyfin/jellyfin --version

# C: Jellyfin FFmpeg and Chromaprint
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/ffmpeg -version | head -n 1
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/ffmpeg -buildconf 2>&1 | grep -- --enable-chromaprint

# D/E: installed/loaded plugin and startup errors
find /srv/homelab/appdata/jellyfin/plugins -maxdepth 2 -iname '*Intro*' -print
docker logs jellyfin 2>&1 | grep -Ei 'Intro.?Skipper|plugin' | tail -n 100
docker logs jellyfin 2>&1 | grep -Ei '\[ERR\].*Intro.?Skipper|Intro.?Skipper.*NotSupported|NotSupported.*Intro.?Skipper' || true

# F/G: analysis task and segments (uses the protected local key)
set -a; source /opt/homelab/services/jellyfin/.intro-skipper.env; set +a
JELLYFIN_URL="http://$(sed -n 's/^JELLYFIN_LAN_IP=//p' /opt/homelab/services/jellyfin/.env):8096"
curl --fail -H "X-Emby-Token: ${JELLYFIN_API_KEY}" "${JELLYFIN_URL}/ScheduledTasks" | \
  python3 -m json.tool | grep -A8 -B2 'Detect and Analyze'
curl --fail -H "X-Emby-Token: ${JELLYFIN_API_KEY}" \
  "${JELLYFIN_URL}/MediaSegments/EPISODE_ID" | python3 -m json.tool

# H: health plus a real client playback test; force a transcode if desired
curl --fail "${JELLYFIN_URL}/health"
sudo /opt/homelab/scripts/verify-jellyfin-gpu.sh
```

Beszel continues to provide container uptime, restarts, CPU, memory, and media
disk usage. It does not parse application logs; use the scheduled-task page and
the targeted log commands above to identify active analysis and failures.

### Rollback

Before changing plugin state, run `sudo /opt/homelab/scripts/backup-jellyfin.sh`.
To roll back only this feature, disable automatic detection, uninstall Intro
Skipper in **Dashboard -> Plugins**, restart Jellyfin, remove the Intro Skipper
repository entry, and remove the protected `.intro-skipper.env` so deployment
does not reconcile it. Existing Media Segments are harmless metadata and can
remain. For full state rollback, stop Jellyfin, move the current
`/srv/homelab/appdata/jellyfin` aside, restore the selected
`jellyfin-appdata.tar.gz` into that path, preserve ownership, and start the
unchanged `jellyfin/jellyfin:10.11.11` container.
