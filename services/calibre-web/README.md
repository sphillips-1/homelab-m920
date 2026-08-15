# Calibre-Web

Calibre-Web provides a browser-based interface for browsing, reading, downloading, and managing ebooks from a Calibre library. It runs as the `calibre-web` Docker service and container.

## Storage

- Application configuration and the Calibre-Web database: `/srv/homelab/appdata/calibre-web` → `/config`
- Calibre library, including `metadata.db`: `/srv/homelab/media/ebooks` → `/books`

The ebook library is the one canonical location; do not create a separate Calibre or Calibre-Web media directory.

## Deployment and access

Deploy or redeploy from the repository root on the M920Q:

```bash
sudo ./scripts/create-directories.sh
sudo ./scripts/deploy-services.sh
```

Check the service:

```bash
docker compose -f services/calibre-web/compose.yml ps
docker logs --tail 100 calibre-web
```

The web UI is available at `http://<m920q-lan-ip>:8083` on the LAN or `http://<m920q-tailscale-name-or-ip>:8083` over Tailscale. It is LAN/Tailscale-only: this deployment does not configure public DNS, Cloudflare, a reverse proxy, TLS certificates, router forwarding, or Internet exposure.

## Initial library setup

Calibre-Web uses an existing Calibre library and requires its `metadata.db` database in `/books`. Create or import a Calibre library so that the file exists at:

```text
/srv/homelab/media/ebooks/metadata.db
```

For a new empty library, use Calibre on another machine to create a library in that location through a network share or by copying the resulting library directory to `/srv/homelab/media/ebooks`. For an existing library, copy or restore the entire library directory there, preserving `metadata.db` and the book folders. Do not create an arbitrary SQLite database file.

After the container starts, browse to port `8083`. On the first setup screen, set the Calibre library location to `/books`. The image's initial Calibre-Web credentials are `admin` / `admin123`; change the password immediately. Calibre-Web uses its own authentication; no SSO or Google login is configured.

## Backups

Back up both `/srv/homelab/appdata/calibre-web` and `/srv/homelab/media/ebooks`. The first contains Calibre-Web settings and users; the second contains the Calibre database and ebooks.

## Image

The service uses `lscr.io/linuxserver/calibre-web:latest`, the maintained LinuxServer Calibre-Web image. It maps the documented container port `8083` and uses the documented `/config` and `/books` paths.
