# LAN HTTP proxy

Nginx owns port 80 on the selected M920Q LAN address. Host routing serves
`http://kids.home.arpa/` from the kids portal and `http://jellyfin.home.arpa/`
from Jellyfin's LAN-bound port 8096. Direct IP port 80 continues to reach
Jellyfin. Unknown Host headers return 404. `/healthz` is a proxy-only health
endpoint. WebSocket upgrades, long reads, and unbuffered Jellyfin streaming
are supported. Port 8092 remains a direct fallback for the kids portal.

The proxy joins only `kids_ingress`, outside the Cloudflare `homelab` network.
No public DNS, Cloudflare route, router forwarding, Tailscale service, application
state, or new credentials are created. The encyclopedia remains internal.

Pi-hole local A records on `192.168.4.75` map both names to `192.168.4.27`.
Clients must use Pi-hole DNS; browser secure DNS can bypass local records.

## Deployment

Provision the kids service first, then:

```bash
cd /opt/homelab
LAN_HTTP_IP=192.168.4.27 bash scripts/deploy-lan-proxy.sh
```

The script validates the template before migrating port 80, detects Jellyfin's
current GPU values without reading its protected `.env`, and recreates Jellyfin
only when it still publishes port 80. Jellyfin's repository Compose definition
must publish only LAN port 8096. There is a brief Jellyfin interruption during
this one-time migration. Subsequent executions are idempotent. Normal deployment
reapplies the proxy after the kids service when its `.env` exists.

The ignored `services/lan-proxy/.env` contains `LAN_HTTP_IP`, not a secret.
When changing the server IP, regenerate the Jellyfin host config, update the
kids and proxy environment files, update Pi-hole records, and redeploy.

## Verify and rollback

```bash
dig +short @192.168.4.75 kids.home.arpa
curl -f http://kids.home.arpa/
curl -f http://jellyfin.home.arpa/health
docker compose -f services/lan-proxy/compose.yml ps
```

To roll back the proxy, stop it with `docker compose ... down`; the direct
8092 and 8096 URLs continue to work. To restore Jellyfin's old port-80 behavior,
stop the proxy first, restore Jellyfin's LAN-only `80:8096` publication and
recreate Jellyfin. Never allow both services to publish port 80 simultaneously.
