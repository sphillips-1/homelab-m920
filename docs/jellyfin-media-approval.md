# Jellyfin media approvals and moves

The **Import media** and **Metadata review** Authentik tiles now cover movies
and TV as well as audiobooks. The existing Discord channel, Anna mention and
configured approver IDs are reused. Only an explicit approval starts a transfer.
Rejected sources stay untouched and get a direct-link Discord reply for manual
review. Jellyfin remains LAN-only; review access uses the existing `torrent-users`
policy. Discord permission does not grant a Jellyfin or Authentik account.

## Completed video workflow

1. The importer discovers supported completed video downloads after the existing
   two-minute stability check. It infers TV from `S01E01` filenames, otherwise
   treats the download as a movie, and queries Jellyfin's configured metadata
   providers. File detection does not itself stop or remove any torrent.
2. A Discord post presents up to three movie/series matches and explicitly says
   approval will **move files, stop seeding and remove verified source files**.
   Either configured approver can choose a numbered reaction. Rejecting sends
   the item to the same manual review list as audiobooks.
3. Approval rechecks torrent completion, source fingerprint, selected metadata,
   available storage and duplicates. It stops only torrents belonging to the
   selected complete source; partial selections of a larger torrent are refused.
4. The worker stages video and matching subtitle files outside Jellyfin's watched
   libraries. It checks source size/mtime before and after copying, fsyncs the
   output, and verifies SHA-256. Approved provider IDs are saved in an NFO.
5. Complete files are published with exclusive hard links from staging; existing
   movies and episodes are never overwritten. The worker requests a Jellyfin
   library refresh. A refresh failure does not invalidate verified library files;
   run Scan in Jellyfin if automatic discovery is unavailable.
6. Before removal, every destination checksum and surviving source's size/mtime
   is rechecked. The worker stops/removes the associated torrent records with
   `deleteFiles=false`, then deletes only the verified video/subtitle source
   files. Unrelated files, artwork, old metadata and other extras remain on USB.
   Empty source directories are removed. Successful transfers delete the original
   Discord request and bot reply; unresolved failures remain visible in Discord.

Audiobooks keep their existing **copy to Audiobookshelf and continue seeding**
behavior. Automatically classified duplicates are preserved on USB and do not
implicitly authorize a move or deletion.

## Naming and supported downloads

- Video: MKV, MP4, AVI, MOV, M4V, WebM, TS, MPG and MPEG.
- Subtitles: SRT, ASS, SSA, VTT, SUB, IDX and SUP with the same source filename
  stem, optionally followed by a language/flags suffix such as `.en.forced.srt`.
- Movies: one video per completed-download source. Movie packs must be split
  first. Destination: `movies/Title (Year) [tmdbid-ID]/Title (Year) [tmdbid-ID].mkv`.
- TV: one series per source, each file with one unambiguous `S01E01` episode
  number. Season packs with separate episode files work; multi-episode videos
  and mixed-series packs are refused. Destination: `tv/Series (Year)
  [tmdbid-ID]/Season 01/Series (Year) [tmdbid-ID] - S01E01.mkv`.
- Existing series are located by provider ID (or exact title plus year), and new
  episodes are added to their managed `/media/tv` path. Existing episodes are
  skipped, including already cataloged episode numbers; their source files are
  retained because they were not copied by the new transfer.
- Provider IDs and exact title/year matches prevent duplicate movies. TV
  duplicate detection is per episode, so an existing series can receive new
  episodes. Download NFO identifiers or an explicit filename title/year are
  checked before posting; unknown filenames still require metadata review.
- Separate audio/video bundles, archives, symlinks and nonregular files are
  refused. The manual form supports title/year lookup and an explicit manual
  metadata confirmation; provider matches are preferred for reliable identity.

## Storage and credentials

The importer uses `/srv/homelab/storage` as a single `/jellymedia` bind so its
staging files and final media can be linked on the same filesystem. Its code
writes destinations only under `movies`, `tv` and `.jellyfin-imports`. Jellyfin's
own existing mounts remain read-only at `/media/movies` and `/media/tv`.
Provisioning verifies the expected external filesystem UUID for those roots and
creates `.jellyfin-imports` with UID/GID 1000 and mode 0750. Missing/wrong storage
fails closed; Compose does not create missing mount sources.

The importer's USB mount is now writable to perform the approved video move.
Audiobook code still preserves its source files. The existing private
`services/jellyfin/.intro-skipper.env` supplies `JELLYFIN_API_KEY`; the importer
uses it internally at `http://jellyfin:8096`. No token is committed, and no new
public Jellyfin endpoint or callback is added. Deploy only through the existing
GitHub Actions workflow.

`imports.sqlite` stores jobs and metadata selections, plus `video_transfers`
containing source snapshots, destination checksums and associated torrent hashes.
All of this remains under `/srv/homelab/appdata/audiobook-importer`, outside Git.
The Discord queue records the media type and job association.

## Recovery

A published transfer whose source cleanup fails becomes **cleanup_required**.
It remains in the review list, and **Finish move** on the import page retries
checksum/ownership verification and cleanup without copying or overwriting the
library again. Changed files or new torrent ownership stop cleanup. This also
works after a container restart; completed jobs refuse further cleanup requests.

An interruption before publication is marked interrupted and needs manual
review. Inspect both the destination and `.jellyfin-imports/<job-id>` before
retrying a partially published job. No automatic restart recovery deletes
sources based only on a destination folder's presence. Failed transfers may
leave their torrent stopped; source files are preserved until verified cleanup.

Run `python3 -B tests/test_video_import.py` for disposable-file regression tests.
Live API checks can verify credentials, metadata previews and library mappings
without approving any real video. End-to-end real-media moves require an
approver's normal Discord or manual-page approval.

Naming and NFO behavior follow the official Jellyfin documentation for
[movies](https://jellyfin.org/docs/general/server/media/movies/),
[TV](https://jellyfin.org/docs/general/server/media/shows/) and
[NFO metadata](https://jellyfin.org/docs/general/server/metadata/nfo/).

## Resolved Discord messages

Successful imports/moves and confirmed `already_in_library` duplicates resolve
the review. The bot deletes its original request and any rejection-link reply,
including older resolved reviews on deployment. Rejected items awaiting manual
review, failures, interruptions and transfers awaiting source cleanup keep their
messages. Deletion retries after errors; a Discord 404 counts as already deleted.
Message IDs and decisions remain in the persistent queue for audit and restart
safety, so deleting a message never causes a replacement post. Only the bot's
tracked review messages are deleted; media files are unaffected by this cleanup.
