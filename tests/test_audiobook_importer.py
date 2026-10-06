"""Exercise import safety without touching real downloads or library data."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import urllib.request
import urllib.error
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('importer', ROOT / 'services/qbittorrent-m920/importer.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'complete' / 'Book'
        self.source.mkdir(parents=True)
        (self.source / 'track.mp3').write_bytes(b'audio fixture')
        (self.source / 'cover.jpg').write_bytes(b'cover fixture')
        (self.source / 'unrelated.exe').write_bytes(b'do not copy')
        self.library = self.root / 'library'
        self.stage = self.root / 'staging'
        self.library.mkdir()
        self.stage.mkdir()
        for name, value in [('LIBRARY', self.library), ('STAGING', self.stage),
                            ('STATE', self.root / 'state'),
                            ('storage_ready', lambda: None), ('torrents', lambda: [])]:
            p = patch.object(app, name, value)
            p.start()
            self.addCleanup(p.stop)
        app.initialize()

    def test_copy_preserves_usb_and_publishes_complete_book(self):
        destination = app.destination('Author', 'Title')
        app.copy_book(self.source, destination, self.stage / 'job')
        self.assertEqual((destination / 'track.mp3').read_bytes(), b'audio fixture')
        self.assertTrue((destination / 'cover.jpg').exists())
        self.assertFalse((destination / 'unrelated.exe').exists())
        self.assertTrue((self.source / 'track.mp3').exists())
        self.assertFalse((self.stage / 'job').exists())
        with self.assertRaises(ValueError):
            app.destination('Author', 'Title')

    def test_incomplete_or_checking_torrent_is_rejected(self):
        for progress, state in [(0.5, 'downloading'), (1, 'checkingUP')]:
            with self.assertRaises(ValueError):
                app.ensure_complete(self.source, [{'content_path': str(self.source),
                                                   'progress': progress, 'state': state}])

    def test_failed_copy_never_publishes_partial_book(self):
        destination = app.destination('Author', 'Title')
        with patch.object(app.shutil, 'copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                app.copy_book(self.source, destination, self.stage / 'job')
        self.assertFalse(destination.exists())
        self.assertFalse((self.stage / 'job').exists())
        self.assertTrue((self.source / 'track.mp3').exists())

    def test_symlink_and_traversal_rejected(self):
        for value in ['../outside', 'Author/Other', '..', 'x\\y']:
            with self.assertRaises(ValueError):
                app.component(value)
        (self.source / 'link.mp3').symlink_to(self.source / 'track.mp3')
        with self.assertRaises(ValueError):
            app.source_files(self.source)
        (self.library / 'Author').symlink_to(self.stage, target_is_directory=True)
        with self.assertRaises(ValueError):
            app.destination('Author', 'Title')

    def test_plain_audio_file_import(self):
        source = self.source / 'track.mp3'
        destination = app.destination('Author', 'Title')
        app.copy_book(source, destination, self.stage / 'job')
        self.assertEqual((destination / 'track.mp3').read_bytes(), source.read_bytes())

    def test_http_requires_verified_identity_and_same_origin(self):
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        for path, headers, body in [
            ('/imports/api/downloads', {}, None),
            ('/imports/api/import', {'X-Authentik-Email': 'owner@example.invalid',
                                    'X-Authentik-Groups': 'torrent-users',
                                    'Content-Type': 'application/json',
                                    'Origin': 'https://evil.example.invalid'}, b'{}'),
            ('/imports/api/import', {'X-Authentik-Email': 'reader@example.invalid',
                                    'X-Authentik-Groups': 'books-users'}, b'{}'),
        ]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(base + path, data=body,
                                                             headers=headers))
            self.assertEqual(error.exception.code, 403)

    def test_metadata_review_is_required_and_cannot_be_reused_with_edits(self):
        with self.assertRaises(ValueError):
            app.reviewed_metadata({}, 'Author', 'Title')
        with app.database() as db:
            db.execute('INSERT INTO reviews VALUES (?, ?, ?, ?, ?)',
                       ('match', 'Author', 'Title', json.dumps({'title': 'Title'}), 9999999999))
        self.assertEqual(app.reviewed_metadata({'review': 'match'}, 'Author', 'Title'),
                         {'title': 'Title'})
        with self.assertRaises(ValueError):
            app.reviewed_metadata({'review': 'match'}, 'Author', 'Different title')
        self.assertEqual(app.reviewed_metadata({'manual': True}, 'Author', 'Title'),
                         {'title': 'Title', 'authors': ['Author']})

    def test_reviewed_metadata_overrides_only_the_copy(self):
        original = {'metadata': {'title': 'Wrong title'}, 'chapters': [{'start': 0, 'end': 10}]}
        (self.source / 'metadata.json').write_text(json.dumps(original))
        target = app.destination('Author', 'Title')
        app.copy_book(self.source, target, self.stage / 'job', {'title': 'Title',
                                                              'authors': ['Author']})
        imported = json.loads((target / 'metadata.json').read_text())
        self.assertEqual(imported['title'], 'Title')
        self.assertEqual(imported['chapters'], original['chapters'])
        self.assertNotIn('metadata', imported)
        self.assertEqual(json.loads((self.source / 'metadata.json').read_text()), original)

    def test_abs_search_previews_without_publishing_a_book(self):
        data = [{'title': 'Title', 'author': 'Author', 'narrator': 'Narrator',
                 'series': [{'series': 'Series', 'sequence': '2'}], 'asin': 'B000000001'}]
        with patch.object(app.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            result = app.metadata_search({'author': 'Author', 'title': 'Title', 'provider': 'audible'})
        self.assertEqual(result[0]['metadata']['narrators'], ['Narrator'])
        self.assertEqual(result[0]['metadata']['series'], ['Series #2'])
        self.assertFalse((self.library / 'Author').exists())
        self.assertEqual(app.reviewed_metadata({'review': result[0]['id']}, 'Author', 'Title')['asin'],
                         'B000000001')

if __name__ == '__main__':
    unittest.main(verbosity=2)
