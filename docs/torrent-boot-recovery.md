# Torrent boot recovery

qBittorrent declares Pi-hole (`192.168.4.75`, see network inventory) as its
external DNS server rather than inheriting a potentially empty DHCP resolver
configuration during boot. Docker service-name resolution remains available.
No public fallback resolver bypasses Pi-hole.

Deployment installs and enables `homelab-torrent-recovery.service`, which runs
after Docker starts and again when Docker is restarted through systemd. It
checks the dedicated USB, waits for qBittorrent's DNS/API health, then recreates
the gateway and importer to join its current network namespace. It shares the
release deployment lock, retries failures after 30 seconds, and does not
restart unrelated applications. Missing USB storage fails closed.

The deployment pipeline runs the same recovery sequence and verifies external
DNS, outbound HTTPS, the local API, importer health, and an anonymous gateway
redirect to SSO from the application namespace. No torrents are added for tests.
DHT node counts are diagnostic only because bootstrap can take time.

Operations:

```bash
systemctl status homelab-torrent-recovery.service
sudo journalctl -u homelab-torrent-recovery.service -b
sudo systemctl start homelab-torrent-recovery.service
sudo bash /opt/homelab/scripts/verify-torrent-connectivity.sh
```

A successful oneshot becomes inactive; that is expected. Health checks alone
do not trigger Docker restarts. This unit handles boot and systemd Docker
restarts; after manually restarting/recreating qBittorrent, run the recovery
unit to reattach its sidecars. Do not run recovery directly during deployment.
To disable boot recovery, use `sudo systemctl disable --now
homelab-torrent-recovery.service`; the next deployment enables it again.

The earlier Jellyfin LAN-address guard remains independent. Validate a real
reboot during a planned maintenance window; pipeline deployment does not reboot
the host.
