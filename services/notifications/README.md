# New audiobook notifications

Flow: Audiobookshelf library API → book watcher → Apprise → ntfy → phones.
ABS 2.36.0 has podcast/backup events but no new-book event, so this service polls
all book libraries once per minute and ignores ebook-only items. Set `LIBRARY_IDS`
on the watcher to restrict subscriptions to comma-separated library IDs.

The first successful complete scan silently records existing audiobooks. New
items must remain unchanged for five minutes before delivery; metadata and audio
size/count/duration changes restart that delay. This is a settling heuristic,
not a guarantee that an upload has finished. Metadata edits to already announced
books do not send another alert. Deleted pending items are cancelled. Successful
deliveries are saved individually; failures retry. A crash after delivery but
before saving can produce a duplicate (at-least-once delivery). A recreated ABS
item with a new ID is treated as a new book.

Persistent state and private credentials live under
`/srv/homelab/appdata/notifications`. Do not delete `watcher/books.json` unless
you intentionally want to rebaseline. Invalid state fails closed. Back up this
directory with other appdata; it contains book metadata and credentials.

## Enable

The deployment pipeline initializes and reconciles this stack automatically.
Reuse of the existing ABS automation token was approved on 2026-10-12.

After service files are deployed under `/opt/homelab`:

```sh
sudo python3 /opt/homelab/scripts/setup-book-notifications.py
```

This idempotently creates private publisher and family passwords, obtains the
existing ABS automation API token, creates ntfy accounts, and starts only these
services. The publisher can write `new-books`; the family can only read it.
Anonymous access is denied. No host ports or public Apprise endpoint are exposed.
The existing ABS automation token is reused; rotate `secrets/abs-token` when that
token changes. Global deployments reconcile this stack after it is initialized.

`notifications.shelfgoblin.dev` routes directly to ntfy in SSO mode. ntfy uses
its native credentials so phone apps can connect without a browser SSO redirect.
Terraform manages its DNS record. Safe/test/access modes do not expose it.
Apprise is stateless and private on the homelab Docker network.

## Subscribe on a phone

Install the ntfy Android or iOS app. Add server
`https://notifications.shelfgoblin.dev`, username `family`, and the password read
locally using `sudo cat /srv/homelab/appdata/notifications/secrets/family-password`.
Subscribe to topic `new-books`. Everyone subscribing to this topic receives the
same audiobook additions. These notifications appear in ntfy, not inside the ABS
mobile app. iOS wake-up requests go through ntfy.sh; book content remains on the
self-hosted server. Phones must be subscribed before a delivery test is useful.

## Operate

```sh
docker logs --tail 30 book-notifications
docker exec book-notifications python -B /app/watch.py --test
docker compose -f /opt/homelab/services/notifications/compose.yml stop
```

The test command sends a clearly labeled push to subscribers. It does not add a
book or change the baseline. Watcher health reflects successful API scans and
delivery processing. Outages of the homelab, internet or DNS delay notifications.

References: [ABS notifications](https://audiobookshelf.org/docs/documentation/server-management/notifications/),
[ntfy configuration and iOS delivery](https://docs.ntfy.sh/config/), and
[Apprise API](https://github.com/caronc/apprise-api).
