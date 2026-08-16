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

Cloudflare Tunnel is the only planned Internet ingress. It makes an outbound
connection from the `cloudflared` container to Cloudflare; the router does not
forward ports 80 or 443. Audiobookshelf and Calibre-Web publish their web ports
on the M920Q host so they are directly reachable on the LAN and through
Tailscale. The `cloudflared` container reaches those same applications directly
over the internal Docker `homelab` network; it does not use their host ports.

Only Audiobookshelf, Calibre-Web, and Authentik are candidates for public routing. SSH,
Docker, databases, Tailscale, and other host services are never exposed through
Cloudflare. Permanent unauthenticated Internet access is not intended.
Authentik is the identity layer; future public application access will be
protected by Authentik/Google SSO.

In **safe** mode, the two application hostnames return 404 while Authentik is
routed. Test mode is deliberately temporary and must be protected by a
Cloudflare Access application.
