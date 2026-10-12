# Audiobookshelf notifications

The external ntfy/Apprise notification stack was retired on 2026-10-12 because
the desired experience is notifications served within Audiobookshelf itself.
Deployment removes its containers and no longer exposes its tunnel route.
Private credentials and watcher state under
`/srv/homelab/appdata/notifications` are retained, outside Git. The existing ABS
automation token remains valid for its original uses.

The retired `notifications` DNS record remains reserved because the production
Terraform pipeline rejects resource deletion. The hostname has no application
route and falls through to the tunnel's 404 response.

ABS 2.36.0 has an outgoing Apprise notification API, but no supported endpoint
for publishing new-book messages to its native phone clients. Native in-app or
phone push notifications require server and client feature work. A notification
inbox added to the ABS website would be a separate implementation and would not
appear in native clients automatically. Replacement implementation is pending
the choice of client experience.

Reference: [ABS notifications](https://audiobookshelf.org/docs/documentation/server-management/notifications/).
