# Audiobookshelf runtime repair

The November 25, 2026 audit found that Audiobookshelf 2.36.0 stored seven
records per audio file in 150 of 282 books. The runtime repair collapses
these records by path and recalculates duration from the distinct tracks.
It preserves book and library item IDs, audio bytes, and listening history.
It retains chapter markers within the corrected duration and maps unfinished
resume positions recorded against the inflated duration back to the surviving
track. It leaves Audible edition metadata as stored.

1. Merge the reviewed change to `main`. In GitHub Actions, run
   **Audiobookshelf Runtime Repair** in **dry-run** mode on `main`.
2. Review the reported book, chapter, and resume counts. Use the book count
   as **expected_count** in **apply** mode during a short playback outage.
3. The workflow stops Audiobookshelf, verifies a SQLite backup under
   `/srv/homelab/backups/abs-runtime-repair.*`, and applies the repair in one
   transaction. It restarts Audiobookshelf, waits for a healthy status, and
   checks for remaining repeated tracks.
4. Check playback and chapter navigation on an affected title after the run.

If recovery is needed, preserve the live database and its SQLite sidecar files
before using the pre-repair backup through the production recovery process.
Restoring the backup would revert catalog and progress changes made after it
was captured. See [recovery](recovery.md).
