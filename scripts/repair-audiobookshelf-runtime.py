"""Repair the verified sevenfold track duplication in Audiobookshelf 2.36.0."""

import argparse
import bisect
import collections
import json
import math
import os
from pathlib import Path
import sqlite3


def distinct_files(files, ignored_fields):
    by_path = {}
    for item in files:
        path = item["metadata"]["path"]
        original = by_path.setdefault(path, item)
        if original is item:
            continue
        if any(original.get(key) != item.get(key)
               for key in original.keys() | item.keys() if key not in ignored_fields):
            raise ValueError("Repeated file records differ in meaningful metadata")
    return by_path


def repair_chapters(chapters, duration):
    # Keep chapter titles and timestamps within the surviving playback range.
    return [
        dict(chapter, end=min(chapter["end"], duration))
        for chapter in chapters
        if chapter["start"] < duration and chapter["end"] > chapter["start"]
    ]


def run(database, backup, expected_count, require_clean=False):
    apply = backup is not None
    mode = "rw" if apply else "ro"
    with sqlite3.connect(f"{database.resolve().as_uri()}?mode={mode}", uri=True) as db:
        db.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        repairs = []
        summary = collections.Counter()
        for item_id, book_id, raw_tracks, raw_files, raw_chapters, old_duration in db.execute(
            """SELECT i.id, b.id, b.audioFiles, i.libraryFiles, b.chapters, b.duration
                 FROM libraryItems i JOIN books b ON b.id = i.mediaId
                WHERE i.mediaType = 'book' AND NOT i.isMissing AND NOT i.isInvalid
                  AND json_array_length(b.audioFiles) > 0"""
        ):
            tracks = json.loads(raw_tracks)
            paths = [track["metadata"]["path"] for track in tracks]
            counts = collections.Counter(paths)
            if len(counts) == len(tracks):
                continue
            if set(counts.values()) != {7}:
                raise ValueError("Found a repetition pattern other than seven copies")
            audio = distinct_files(tracks, {"index", "addedAt", "updatedAt"})
            library = distinct_files(json.loads(raw_files), {"addedAt", "updatedAt"})
            if not audio.keys() <= library.keys():
                raise ValueError("A track is absent from the library file records")

            offsets = {}
            duration = 0.0
            clean_tracks = []
            for track in audio.values():
                seconds = track["duration"]
                if not math.isfinite(seconds) or seconds <= 0 or track.get("exclude") or track.get("error"):
                    raise ValueError("Cannot safely rebuild offsets for an excluded or invalid track")
                offsets[track["metadata"]["path"]] = duration
                duration += seconds
                clean_tracks.append(dict(track, index=len(clean_tracks) + 1))
            if not math.isclose(old_duration, duration * 7, abs_tol=0.1):
                raise ValueError("Stored duration does not match seven copies of the tracks")

            chapters = json.loads(raw_chapters or "[]")
            clean_chapters = repair_chapters(chapters, duration)
            summary["chapter_ranges_adjusted"] += clean_chapters != chapters
            old_offsets = [0.0]
            for track in tracks:
                old_offsets.append(old_offsets[-1] + track["duration"])
            progress_updates = []
            for progress_id, progress_duration, position, finished in db.execute(
                """SELECT id, duration, currentTime, isFinished FROM mediaProgresses
                    WHERE mediaItemType = 'book' AND mediaItemId = ?""",
                (book_id,),
            ):
                if finished or not math.isclose(progress_duration or 0, old_duration, abs_tol=2):
                    continue
                if position is None or not 0 <= position <= old_duration + 1:
                    raise ValueError("An active resume position cannot be safely mapped")
                index = min(bisect.bisect_right(old_offsets, position) - 1, len(paths) - 1)
                corrected = min(duration, offsets[paths[index]] + position - old_offsets[index])
                progress_updates.append((duration, corrected, progress_id))
            summary["resume_positions_adjusted"] += len(progress_updates)
            summary["repeated_tracks_removed"] += len(tracks) - len(clean_tracks)
            repairs.append((book_id, item_id, clean_tracks, list(library.values()),
                            clean_chapters, duration, progress_updates))

        summary["affected_books"] = len(repairs)
        print(json.dumps(summary, sort_keys=True), flush=True)
        if require_clean and repairs:
            raise ValueError("Repeated tracks remain after repair")
        if not apply or not repairs:
            return
        if len(repairs) != expected_count:
            raise ValueError("Affected count differs from the approved dry run")

        # Read from a separate connection so SQLite backs up committed pre-repair state.
        fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True) as source:
            with sqlite3.connect(backup) as destination:
                source.backup(destination)
                if destination.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("Pre-repair backup failed its integrity check")
        print("Verified pre-repair SQLite backup created", flush=True)

        for book, item, tracks, files, chapters, duration, progress in repairs:
            db.execute("UPDATE books SET audioFiles=?, chapters=?, duration=? WHERE id=?",
                       (json.dumps(tracks), json.dumps(chapters), duration, book))
            db.execute("UPDATE libraryItems SET libraryFiles=? WHERE id=?",
                       (json.dumps(files), item))
            db.executemany("UPDATE mediaProgresses SET duration=?, currentTime=? WHERE id=?", progress)
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("Repaired database failed its integrity check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--require-clean", action="store_true")
    arguments = parser.parse_args()
    if arguments.backup and not arguments.expected_count:
        parser.error("--backup requires a positive --expected-count")
    run(arguments.database, arguments.backup, arguments.expected_count, arguments.require_clean)
