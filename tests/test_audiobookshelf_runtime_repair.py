import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/repair-audiobookshelf-runtime.py"
SPEC = importlib.util.spec_from_file_location("runtime_repair", SOURCE)
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


class RuntimeRepairTest(unittest.TestCase):
    def test_backup_and_repair_preserve_ids_and_map_resume_position(self):
        with tempfile.TemporaryDirectory() as temp:
            live = Path(temp) / "live.sqlite"
            backup = Path(temp) / "backup.sqlite"
            with sqlite3.connect(live) as db:
                db.executescript("""
                    CREATE TABLE books(id, audioFiles, chapters, duration);
                    CREATE TABLE libraryItems(id, mediaId, libraryFiles, mediaType, isMissing, isInvalid);
                    CREATE TABLE mediaProgresses(id, mediaItemId, mediaItemType, duration, currentTime, isFinished);
                    INSERT INTO mediaProgresses VALUES (3, 1, 'book', 210, 45, 0);
                    INSERT INTO mediaProgresses VALUES (4, 1, 'book', 210, 200, 1);
                """)
                tracks = [
                    {"metadata": {"path": f"/audiobooks/test/{n % 2}.mp3"},
                     "duration": 10 if n % 2 == 0 else 20, "index": n + 1}
                    for n in range(14)
                ]
                files = [{"metadata": track["metadata"], "addedAt": n} for n, track in enumerate(tracks)]
                chapters = [{"id": 0, "start": 0, "end": 35}, {"id": 1, "start": 35, "end": 210}]
                db.execute("INSERT INTO books VALUES (1, ?, ?, 210)", (json.dumps(tracks), json.dumps(chapters)))
                db.execute("INSERT INTO libraryItems VALUES (2, 1, ?, 'book', 0, 0)", (json.dumps(files),))

            repair.run(live, None, 0)
            with self.assertRaisesRegex(ValueError, "approved dry run"):
                repair.run(live, backup, 2)
            self.assertFalse(backup.exists())
            repair.run(live, backup, 1)
            repair.run(live, None, 0, require_clean=True)

            with sqlite3.connect(live) as db:
                book_id, audio, chapters, duration = db.execute("SELECT * FROM books").fetchone()
                self.assertEqual((book_id, duration), (1, 30))
                self.assertEqual([track["index"] for track in json.loads(audio)], [1, 2])
                self.assertEqual(json.loads(chapters), [{"id": 0, "start": 0, "end": 30}])
                self.assertEqual(db.execute("SELECT id, json_array_length(libraryFiles) FROM libraryItems").fetchone(), (2, 2))
                self.assertEqual(
                    db.execute("SELECT duration, currentTime, isFinished FROM mediaProgresses ORDER BY id").fetchall(),
                    [(30, 15, 0), (210, 200, 1)],
                )
            with sqlite3.connect(backup) as db:
                self.assertEqual(db.execute("SELECT json_array_length(audioFiles), duration FROM books").fetchone(), (14, 210))


if __name__ == "__main__":
    unittest.main()
