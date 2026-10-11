# Pi-hole DNS outage monitoring

The M920Q queries Pi-hole (`192.168.4.75`) for `example.com` every 60 seconds. Three consecutive failed DNS checks produce one outage message in **Phillips Collab Area / #pihole**. The first successful check after an announced outage produces one recovery message. Successful checks and brief failures are silent. Detection normally takes about two to three minutes plus query timeouts.

The container uses public resolvers `1.1.1.1` and `9.9.9.9` for Discord, independently of the explicit Pi-hole query. No host DNS settings change. This checks DNS resolution availability, not whether filtering is enabled or whether every upstream lookup works; cached answers may still succeed during an upstream outage.

## Storage and credentials

- Source: `/opt/homelab/services/pihole-monitor`.
- Webhook: `/srv/homelab/appdata/monitoring/pihole/discord-webhook.url`, mode `0600`.
- State: `/srv/homelab/appdata/monitoring/pihole/state/state.json`.
- Both persistent directories are private (`0700`). No credentials or generated state belong in Git.

The process runs as UID/GID 1000 (the verified `sean` account on this M920Q), with all capabilities dropped and a read-only root filesystem. Override `PIHOLE_MONITOR_UID` and `PIHOLE_MONITOR_GID` in an ignored service `.env` if the account changes; the webhook and state must belong to that UID/GID.

Outage state survives container restarts. Failed notifications retry on the next check. Health checks track whether the monitor loop is running; a Pi-hole outage does not mark the monitor itself unhealthy. Notification delivery failures are logged without exposing the webhook.

## Deployment and operations

Enter or rotate the webhook from Windows with `scripts/configure-pihole-discord.ps1`. Then recreate the monitor: the helper atomically replaces the credential file, so an existing file bind mount must be refreshed.

```bash
docker compose -f /opt/homelab/services/pihole-monitor/compose.yml up -d --force-recreate
docker logs --tail 20 pihole-monitor
docker exec pihole-monitor python -B /app/monitor.py --check
```

The repository deployment script starts this service only when a nonempty webhook exists, and restarts it to load Python source changes. Service verification checks monitor health. Docker's `unless-stopped` policy starts it after reboot unless it was explicitly stopped.

To send clearly labeled outage and recovery tests without disrupting Pi-hole or altering production outage state:

```bash
docker exec pihole-monitor python -B /app/monitor.py --test-notifications
```

Transition tests: `python3 -B tests/test_pihole_monitor.py`. They cover the failure threshold, brief failures, duplicate suppression after restart, recovery, and retry after failed outage/recovery delivery.

To disable monitoring, stop this Compose service; Pi-hole itself is unaffected. This local monitor cannot send alerts when the M920Q, home internet connection, or household power is down. Detecting those requires an independent external heartbeat monitor.

## Initial deployment

On 2026-10-11 the new service files were copied directly from the working repository to `/opt/homelab/services/pihole-monitor` and only this container was started. Live DNS and two labeled Discord notifications succeeded. Existing application containers and Pi-hole were not restarted. The repository deployment hooks manage this service on subsequent main deployments.
