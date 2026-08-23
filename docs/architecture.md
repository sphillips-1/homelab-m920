# Architecture

## Host

The M920Q is the primary Homelab server.

```text
M920Q
├── Debian 13
├── Docker
├── Tailscale
├── Cloudflare Tunnel (outbound-only public ingress)
├── Beszel container monitoring (private LAN/Tailscale access)
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

Only Audiobookshelf, Calibre-Web, Beszel, and Authentik are candidates for public
routing. SSH, Docker, databases, Tailscale, and other host services are never
exposed through Cloudflare. Permanent unauthenticated Internet access is not
intended. Authentik is the single application identity and authorization
provider: its embedded proxy protects Calibre-Web and its OIDC provider serves
Audiobookshelf browser/mobile clients. Cloudflare remains the DNS and Tunnel
edge. Entra External ID is pending decommission.

Beszel provides the container status page on host port 8090 for LAN and
Tailscale clients. Public access at `status.shelfgoblin.dev` passes through the
Authentik embedded proxy. Its local agent reads the Docker socket read-only and
communicates with the dashboard through a Unix socket; no agent port is exposed.

In **safe** mode, the application hostnames return 404 while Authentik is
routed. In normal **sso** mode, public application access uses Authentik without
changing LAN or Tailscale routes.
