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
