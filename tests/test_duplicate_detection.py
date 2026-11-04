"""Duplicate identity regressions without real media, network or application state."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('duplicate_importer', ROOT / 'services/qbittorrent-m920/importer.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def syncsafe(size):
    return bytes((size >> shift) & 127 for shift in (21, 14, 7, 0))


def tagged_mp3(path, title, author, version=3):
    frames = b''
    for name, value in [(b'TIT2', title), (b'TPE1', author)]:
        data = b'\x03' + value.encode('utf-8') if version == 4 else b'\x01' + value.encode('utf-16')
        length = syncsafe(len(data)) if version == 4 else len(data).to_bytes(4, 'big')
        frames += name + length + b'\0\0' + data
    path.write_bytes(b'ID3' + bytes([version, 0, 0]) + syncsafe(len(frames)) + frames + b'audio fixture')


class DuplicateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        self.library.mkdir()
        self.downloads = self.root / 'downloads'
        (self.downloads / 'complete').mkdir(parents=True)
        self.source = self.downloads / 'complete' / 'Rule Of Two (Book 2).mp3'
        tagged_mp3(self.source, 'Rule of Two (Book 02)', 'Drew Karpyshyn')
        for name, value in [('LIBRARY', self.library), ('DOWNLOADS', self.downloads),
                            ('_library_identity_cache', None)]:
            p = patch.object(app, name, value)
            p.start()
            self.addCleanup(p.stop)

    def book(self, author='Drew Karpyshyn', title='Rule of Two'):
        path = self.library / author / title
        path.mkdir(parents=True)
        (path / 'different-name.m4b').write_bytes(b'different encoding')
        return path

    def test_rule_of_two_is_detected_across_filename_format_and_book_suffix(self):
        self.book()
        self.assertEqual(app.existing_book(self.source), 'Drew Karpyshyn/Rule of Two')

    def test_same_title_different_author_is_not_a_duplicate(self):
        self.book(author='Another Author')
        self.assertIsNone(app.existing_book(self.source))

    def test_untagged_filename_alone_is_not_enough_to_suppress(self):
        self.book()
        self.source.write_bytes(b'no tags')
        self.assertIsNone(app.existing_book(self.source))

    def test_real_title_numbers_and_different_series_positions_are_preserved(self):
        self.book(title='Rule of Three')
        self.book(title='Saga (Book 1)')
        tagged_mp3(self.source, 'Saga (Book 2)', 'Drew Karpyshyn')
        self.assertIsNone(app.existing_book(self.source))

    def test_id3v24_unicode_tags(self):
        self.book(author='Author', title='The Book')
        tagged_mp3(self.source, 'THE BOOK', 'AUTHOR', version=4)
        self.assertEqual(app.existing_book(self.source), 'Author/The Book')

    def test_provider_identifier_matches_even_if_folder_title_differs(self):
        path = self.book(title='Old title')
        (path / 'metadata.json').write_text(json.dumps({'asin': 'B123456789'}))
        self.assertEqual(app.existing_book(self.source, {'asin': 'b123456789'}), 'Drew Karpyshyn/Old title')

    def test_directory_sidecar_identity(self):
        self.book()
        source = self.downloads / 'complete' / 'Unrelated download name'
        source.mkdir()
        (source / 'book.m4b').write_bytes(b'new encoding')
        (source / 'metadata.json').write_text(json.dumps({'metadata': {
            'title': 'RULE OF TWO', 'authors': ['Drew Karpyshyn']}}))
        self.assertEqual(app.existing_book(source), 'Drew Karpyshyn/Rule of Two')

    def test_empty_destination_is_not_an_existing_book(self):
        (self.library / 'Drew Karpyshyn' / 'Rule of Two').mkdir(parents=True)
        self.assertIsNone(app.existing_book(self.source))

    def test_final_metadata_check_refreshes_library_inventory(self):
        self.assertIsNone(app.existing_book(self.source))
        self.book()
        self.assertEqual(app.existing_book(self.source, {'title': 'Rule of Two',
                        'authors': ['Drew Karpyshyn']}), 'Drew Karpyshyn/Rule of Two')

    def test_catalog_hides_existing_book_without_filename_history(self):
        self.book()
        with patch.object(app, 'storage_ready'), patch.object(app, 'torrents', return_value=[]), \
             patch.object(app, 'database') as database:
            database.return_value.__enter__.return_value.execute.return_value = []
            self.assertEqual(app.catalog(), [])

    def test_manual_import_is_rechecked_before_copying(self):
        self.book()
        with patch.object(app, 'catalog', return_value=[{'source': self.source.name}]), \
             patch.object(app.threading, 'Thread') as thread:
            with self.assertRaisesRegex(ValueError, 'Already in the audiobook library'):
                app.start_job({'source': self.source.name, 'author': 'DREW KARPYSHYN',
                               'title': 'Rule of Two (Book 02)', 'manual': True})
            thread.assert_not_called()
            self.assertFalse(app.lock.locked())

    def test_truncated_and_unsupported_tags_are_unknown(self):
        self.source.write_bytes(b'ID3')
        self.assertEqual(app.mp3_identity(self.source), {})
        self.source.write_bytes(b'ID3\x03\0\x80' + syncsafe(100) + b'broken')
        self.assertEqual(app.mp3_identity(self.source), {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
