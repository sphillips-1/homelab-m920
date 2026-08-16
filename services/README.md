# Services

Each service gets its own directory with a Compose definition and service-specific deployment notes.

A service directory should contain the configuration required to deploy that service while persistent state remains under `/srv/homelab/appdata`.

Initial services:

- `audiobookshelf`
- `calibre-web`
- `homepage`
- `monitoring`
- `authentik`

Calibre-Web is deployed with the other services by `scripts/deploy-services.sh`. Its persistent state is under `/srv/homelab/appdata/calibre-web`; its Calibre library is under `/srv/homelab/media/ebooks`.
