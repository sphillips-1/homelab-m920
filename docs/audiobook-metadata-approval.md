# Audiobook metadata approval

Movies and TV now share this Discord/manual-review process. See
[Jellyfin approvals and moves](jellyfin-media-approval.md) for their explicit
move-and-stop-seeding policy; audiobook originals remain available for seeding.

## Review flow

The existing `audiobook-importer` polls completed USB downloads every 30 seconds.
Only ordinary audio files accepted by its storage and torrent completion checks
are considered. Each download must remain unchanged for two minutes. Initial
activation also discovers completed downloads that have not already been imported.

Before posting, the importer checks actual audio-bearing library folders using
ASIN/ISBN or normalized title plus author. Source identities come from a root
`metadata.json` or consistent embedded MP3 ID3v2.3/2.4 title/artist tags. Case,
punctuation and trailing `(Book 02)` annotations are normalized; distinct title
numbers, conflicting series positions and different authors remain distinct.
Filename or title similarity alone never silently suppresses a download.
Unsupported or missing tags keep the normal review flow. Library identities are
cached for at most 30 seconds and refreshed for the final import check.

Confirmed duplicates are hidden from the download picker and marked
`already_in_library` in the queue. Existing Discord requests and rejection
replies are updated, and duplicates leave the manual review list. Files stay
on USB for seeding. Both Discord approvals and web imports are checked again
before copying, including books imported under different source names.

The worker reads a root `metadata.json` and embedded MP3 tags when available, otherwise uses the
filename (including an `Author - Title` naming convention), and searches the
existing Audiobookshelf Audible provider. Up to three editions are saved with
their author, title, narrator, series, publisher, year, language and ASIN.
These are suggestions, not verification of the audio's edition.

A bot posts in **#media-approval** (`1567517842658558083`) and mentions **Anna**
(`490205210145194009`). Anna is the sole Discord approver in the example
configuration. Numbered reactions **1️⃣ / 2️⃣ / 3️⃣** approve the corresponding
edition; **❌** rejects the proposed metadata. Votes from other users and bots
are ignored. Multiple conflicting choices remain pending until only one choice
remains. Reactions are polled through Discord's REST API; no incoming Discord
webhook, public callback, Gateway connection or privileged intent is needed.

Approval uses the exact stored metadata and the existing copy/scan workflow.
The worker rechecks completion, source fingerprint and existing jobs. Changed
downloads and uncertain recovery states require manual review. Copies remain
serialized. The original message is updated as the import finishes or fails.

Rejection never removes files or stops seeding. It adds the download to
**Metadata review**, a restricted Authentik portal tile. The bot replies to the
original message with a direct link to that item. Open the item to inspect file
names/sizes, the existing metadata sidecar and saved provider candidates; edit
the author/title, search Audible, Google Books or Open Library, and select an
edition. The author may be blank for title-only searches; selecting a match
fills its author. A manual import still needs an author for library organization.
**Approve and import** completes the manual review. The explicit manual
confirmation remains available when no provider matches the audio. Importing
removes the item from the review list; a failed/interrupted import returns there.
When automatic search finds no candidates, the Discord post offers rejection
to this manual workflow rather than an approval without metadata.

The tile and review URLs inherit the importer's `torrent-users` access policy.
Discord user IDs do not grant Authentik access; a person opening a review link
must already have an authorized Authentik account.

## Private bot setup and deployment

1. Create a Discord application bot and invite it into the server. Give it
   **View Channel**, **Send Messages**, **Read Message History** and **Add
   Reactions** in #media-approval. Use a bot token, not the existing Pi-hole
   notification webhook. It does not require Administrator or Manage Messages.
2. Copy `services/qbittorrent-m920/discord-approval.json.example` into a private
   editor, replace the placeholder token, and save the complete JSON as GitHub
   Actions environment secret **DISCORD_MEDIA_APPROVAL_CONFIG** in the existing
   **infrastructure** environment. The supplied channel and Anna IDs are already
   populated. Do not save the completed configuration in Git or paste it in chat.
3. Deploy the reviewed commit through the normal **Deploy** GitHub Actions
   workflow. Its self-hosted container job installs the configuration through
   stdin into the running importer, with mode `0600`, then restarts that
   container. There is no direct SSH deployment step. The workflow preserves an
   existing private configuration when the secret is absent. To disable the
   worker, remove the private configuration and restart through a reviewed
   pipeline change; simply removing the Actions secret does not disable it.
4. Verify with one completed audiobook: Anna receives a mention, unauthorized
   reactions do nothing, approval imports the selected edition, and rejection
   produces a threaded reply linking to the portal-protected review item.

Changing the bot token requires another pipeline run. Keep the channel fixed
while reviews are outstanding: stored message IDs belong to that channel.
Provisioning requires Docker access for the existing self-hosted runner.

## State and recovery

Code and service mounts are rebuildable under `/opt/homelab`. State stays under
`/srv/homelab/appdata/audiobook-importer`:

- `imports.sqlite`: existing copy jobs and short-lived web metadata selections.
- `discord-approvals.sqlite`: discovered sources, fingerprints, stored metadata,
  messages, decisions, deciding user IDs, rejection replies and associated jobs.
- `discord-approval.secret`: private bot configuration, owner UID 1000, mode 0600.

Keep both SQLite databases and the private configuration in encrypted backups.
Stop the importer through the deployment pipeline or use SQLite's backup API
when taking a consistent backup. Restoring only one database can leave records
requiring manual review. Never clear the queue database to retry a single item:
that can rediscover old downloads and repost reviews.

Notification errors retry and leave imports unapproved. Discord rate limits are
respected with cooldowns. Saved message IDs prevent ordinary restart duplicates;
Discord nonces also suppress short retries when a send response is lost. A crash
after Discord accepted a message but before its ID was saved can still duplicate
a notification after Discord's nonce window expires. Only the message attached
to the persisted queue item is actionable. A crash around copy-job startup is
marked `needs_review`, never automatically retried. Failed imports are also
manual-review items; originals and existing destinations are preserved.

The worker logs sanitized error types; it does not log tokens or request headers.
Missing/invalid private configuration disables Discord automation while the
existing web importer continues to work. Check `docker logs audiobook-importer`
if reviews do not arrive. Its existing HTTP healthcheck verifies the web service,
not Discord delivery or bot permissions.

## Validation

Run `python3 -B tests/test_duplicate_detection.py` for library identity and
false-positive regression coverage. Run `python3 -B tests/test_discord_approval.py` for offline queue, authorization,
rejection-link, manual-resolution, recovery and notification-retry coverage.
The deployment workflow runs it alongside the existing importer safety tests.
Live Discord delivery and Authentik tile checks require the private bot
configuration and the normal deployment pipeline.

Discord endpoints follow the official
[Message resource](https://github.com/discord/discord-api-docs/blob/main/developers/resources/message.mdx).
