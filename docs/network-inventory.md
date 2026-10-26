# Network inventory

Use this document as the reference for homelab LAN addresses. These are documented operational addresses, not secrets or generated application state. Update this inventory when an address changes; do not infer current addresses from older examples elsewhere in the repository.

| Device | Role | LAN IPv4 | Access |
| --- | --- | --- | --- |
| Lenovo ThinkCentre M920Q | Primary homelab server; hostname `homelab` | `192.168.4.27` | SSH: `sean@192.168.4.27` |
| Raspberry Pi Zero 2 | Pi-hole DNS server | `192.168.4.75` | DNS: TCP/UDP 53; admin: `http://192.168.4.75/admin/` |

## Kids intranet

- Curiosity Club: `http://192.168.4.27:8092/`, deployed 2026-10-26.
- TCP 8092 binds only to the M920Q LAN address. No Cloudflare route is configured.
- Optional DNS name `kids.home.arpa` is planned, not yet installed in Pi-hole.
  If added, use `http://kids.home.arpa:8092/`; Jellyfin still owns port 80.
- Offline Vikidia is proxied through the portal; its container has no host port.

## Evidence and maintenance

Addresses recovered on 2026-10-11 from the previous chat **Check Pi-hole health**, with successful checks performed on 2026-10-09:

- M920Q: the user corrected the old `.37` address to `.27`; SSH to `sean@192.168.4.27` returned hostname `homelab`.
- Pi-hole: queries from the laptop and M920Q to `192.168.4.75` succeeded. UDP and TCP DNS worked, blocking was confirmed, and the admin page returned HTTP 200.
- `192.168.4.37` is an outdated M920Q address, not the current reference.

These are historically verified addresses, not a fresh live check on 2026-10-11. Eero DHCP reservations have not been verified. Check or create reservations before depending on these addresses for permanent monitoring.

Pi-hole SSH authentication was unsuccessful during the health check; no working SSH username or credentials are documented here.

## DNS outage monitoring

- Discord server: **Phillips Collab Area**
- Discord channel: **#pihole**
- Notification events: DNS outage after three consecutive failed checks, and recovery.
- Check interval: one minute.
- Discord webhook: configured privately on M920Q; keep the URL outside Git.

The planned Discord outage monitor on the M920Q should query Pi-hole explicitly at `192.168.4.75` and use an independent DNS path for notification delivery. Keep Discord webhook URLs outside Git. Monitoring was deployed on 2026-10-11; see [monitor operations](../services/pihole-monitor/README.md).
