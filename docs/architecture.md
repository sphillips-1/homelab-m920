# Architecture

## Host

The M920Q is the primary Homelab server.

```text
M920Q
├── Debian 13
├── Docker
├── Tailscale
├── Cloudflare Tunnel (outbound-only public ingress)
├── /opt/homelab
└── /srv/homelab
```

## Repository

`/opt/homelab` contains rebuildable infrastructure:

- service definitions
- deployment scripts
- Docker configuration
- systemd units
- documentation

## Persistent data

`/srv/homelab` contains state that must survive repository rebuilds:

```text
/srv/homelab/
├── appdata/
├── media/
└── backups/
```

## Service model

Services are kept logically separate so individual applications can be deployed, updated, or recovered without turning the host into one monolithic configuration.

The exact Compose organization will be established as services are migrated.

## Internet ingress

Cloudflare Tunnel is the only planned Internet ingress.  It makes an outbound
connection from the `cloudflared` container to Cloudflare; the router does not
forward ports 80 or 443. Audiobookshelf and Calibre-Web bind only to loopback
on the host and are reachable by the tunnel over the internal Docker `homelab`
network. Tailscale remains the private administration path.

Before Authentik is deployed, the tunnel configuration must remain in **safe**
mode, where all configured hostnames return 404. Test mode is deliberately
temporary and must be protected by a Cloudflare Access application.
