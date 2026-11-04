"""Offline tests: no Discord messages and no real torrent/library changes."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'discord_approval', ROOT / 'services/qbittorrent-m920/discord_approval.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / 'complete' / 'Author - Title'
        source.mkdir(parents=True)
        (source / 'book.m4b').write_bytes(b'fixture')
        def database():
            db = sqlite3.connect(self.root / 'jobs.sqlite')
            db.row_factory = sqlite3.Row
            return db
        with closing(database()) as db:
            db.execute('CREATE TABLE jobs (id TEXT,source TEXT,status TEXT)')
            db.execute('CREATE TABLE reviews (id TEXT,author TEXT,title TEXT,metadata TEXT,expires REAL)')
            db.commit()
        self.match = {'author': 'Author', 'title': 'Title', 'metadata': {
            'title': 'Title', 'authors': ['Author'], 'narrators': ['Narrator']}}
        self.app = types.SimpleNamespace(
            STATE=self.root, DOWNLOADS=self.root, lock=threading.Lock(), database=database,
            catalog=Mock(return_value=[{'source': source.name}]),
            source_files=lambda path: [(path / 'book.m4b', (path / 'book.m4b').stat().st_size,
                                       (path / 'book.m4b').stat().st_mtime_ns)],
            metadata_search=Mock(return_value=[self.match]),
            start_job=Mock(return_value={'id': 'job1'}))
        self.app.component = lambda value: value
        self.app.existing_book = Mock(return_value=None)
        self.app.source_identity = Mock(return_value={})
        self.app.media_kind = Mock(return_value='audiobook')
        self.app.media_name = Mock(return_value='Title')
        self.app.media_year = Mock(return_value=None)
        self.config = {'channel_id': '123', 'notify_user_id': '456',
                       'approver_ids': ['456'], 'bot_token': 'fixture'}
        self.discord = Mock()
        self.discord.request.return_value = {'id': '789'}
        self.discord.voters.return_value = set()
        self.queue = module.ReviewQueue(self.app, self.config, self.discord)

    def row(self):
        with self.queue.db() as db:
            return db.execute('SELECT * FROM queue').fetchone()

    def prepare(self):
        self.queue.tick()
        self.queue.update(self.row()['id'], seen=0)
        self.queue.tick()
        self.queue.tick()
        return self.row()

    def vote(self, emoji, actors):
        self.discord.voters.side_effect = lambda route, value: actors if value == emoji else set()
        self.queue.tick()

    def test_settling_discovery_and_durable_notification(self):
        self.queue.tick()
        self.app.metadata_search.assert_not_called()
        row = self.prepare()
        self.assertEqual(row['status'], 'pending')
        self.assertEqual(row['message'], '789')
        self.app.start_job.assert_not_called()
        module.ReviewQueue(self.app, self.config, self.discord).tick()
        posts = [call for call in self.discord.request.call_args_list if call.args[0] == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].args[2]['allowed_mentions']['users'], ['456'])
        self.assertIn('Narrator', posts[0].args[2]['content'])

    def test_unauthorized_votes_are_ignored(self):
        self.prepare()
        self.vote(module.CHOICES[0], {'999'})
        self.assertEqual(self.row()['status'], 'pending')
        self.app.start_job.assert_not_called()

    def test_approval_uses_stored_metadata_and_copies_once(self):
        self.prepare()
        self.vote(module.CHOICES[0], {'456'})
        self.assertEqual(self.row()['status'], 'approved')
        self.queue.tick()  # update Discord
        self.queue.tick()  # import
        self.assertEqual(self.row()['status'], 'importing')
        payload = self.app.start_job.call_args.args[0]
        with closing(self.app.database()) as db:
            stored = db.execute('SELECT metadata FROM reviews WHERE id=?', (payload['review'],)).fetchone()
        self.assertEqual(json.loads(stored[0]), self.match['metadata'])
        self.queue.tick()
        self.queue.tick()
        self.app.start_job.assert_called_once()

    def test_reject_does_not_import_or_remove_source(self):
        self.prepare()
        self.vote(module.REJECT, {'456'})
        self.queue.tick()
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'rejected')
        self.app.start_job.assert_not_called()
        self.assertTrue((self.root / 'complete' / 'Author - Title' / 'book.m4b').exists())
        posts = [call for call in self.discord.request.call_args_list if call.args[0] == 'POST']
        self.assertEqual(len(posts), 2)
        reply = posts[-1].args[2]
        self.assertEqual(reply['message_reference']['message_id'], '789')
        self.assertIn('/imports/?review=' + self.row()['id'], reply['content'])
        self.assertEqual(module.reviews(self.app)[0]['id'], self.row()['id'])
        detail = module.reviews(self.app, self.row()['id'])
        self.assertEqual(detail['files'][0]['path'], 'book.m4b')
        self.assertEqual(detail['matches'][0]['metadata']['narrators'], ['Narrator'])

    def test_manual_import_resolves_review_and_tracks_job(self):
        self.prepare()
        self.vote(module.REJECT, {'456'})
        key = self.row()['id']
        with self.assertRaises(ValueError):
            module.manual_job(self.app, key, 'Other source')
        module.manual_job(self.app, key, 'Author - Title', 'manual1')
        self.assertEqual(module.reviews(self.app), [])
        with closing(self.app.database()) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?)', ('manual1', 'Author - Title', 'done'))
            db.commit()
        for _ in range(3):
            self.queue.tick()
        self.assertEqual(self.row()['status'], 'done')

    def test_unavailable_download_is_not_sent_for_approval(self):
        self.queue.tick()
        self.queue.update(self.row()['id'], seen=0)
        self.app.catalog.return_value = []
        self.queue.tick()
        self.app.metadata_search.assert_not_called()
        self.discord.request.assert_not_called()

    def test_conflicting_votes_do_not_import(self):
        self.prepare()
        self.discord.voters.return_value = {'456'}
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'pending')

    def test_changed_source_invalidates_approval(self):
        self.prepare()
        self.vote(module.CHOICES[0], {'456'})
        (self.root / 'complete' / 'Author - Title' / 'book.m4b').write_bytes(b'changed')
        self.queue.tick()
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'source_changed')
        self.app.start_job.assert_not_called()

    def test_restart_during_start_requires_manual_review(self):
        self.prepare()
        self.queue.update(self.row()['id'], status='starting')
        module.ReviewQueue(self.app, self.config, self.discord)
        self.assertEqual(self.row()['status'], 'needs_review')

    def test_send_failure_retries_without_approving(self):
        self.queue.tick()
        self.queue.update(self.row()['id'], seen=0)
        self.queue.tick()
        self.discord.request.side_effect = RuntimeError('offline')
        self.queue.tick()
        self.assertIsNone(self.row()['message'])
        self.discord.request.side_effect = None
        self.queue.tick()
        self.assertEqual(self.row()['message'], '789')
        self.app.start_job.assert_not_called()

    def test_no_matches_offers_only_rejection(self):
        self.app.metadata_search.return_value = []
        self.prepare()
        puts = [call for call in self.discord.request.call_args_list if call.args[0] == 'PUT']
        self.assertEqual(len(puts), 1)
        self.assertIn('No usable metadata match', self.queue.content(self.row()))

    def test_existing_library_book_is_not_announced(self):
        self.app.existing_book.return_value = 'Author/Title'
        self.prepare()
        self.assertEqual(self.row()['status'], 'already_in_library')
        self.discord.request.assert_not_called()
        self.app.start_job.assert_not_called()

    def test_rejected_duplicate_is_reconciled_and_messages_deleted(self):
        self.prepare()
        self.vote(module.REJECT, {'456'})
        self.queue.tick()  # rejection reply
        self.app.existing_book.return_value = 'Author/Title'
        self.queue.tick()
        self.queue.tick()
        self.assertEqual(self.row()['status'], 'already_in_library')
        self.assertEqual(module.reviews(self.app), [])
        deletes = [call for call in self.discord.request.call_args_list if call.args[0] == 'DELETE']
        self.assertEqual(len(deletes), 2)
        self.assertEqual(self.row()['discord_deleted'], 1)
        self.app.start_job.assert_not_called()

    def test_approved_metadata_is_rechecked_against_library(self):
        self.prepare()
        self.vote(module.CHOICES[0], {'456'})
        self.app.existing_book.side_effect = lambda source, metadata=None: 'Author/Title' if metadata else None
        self.queue.tick()  # update original message
        self.queue.tick()  # final metadata duplicate check
        self.assertEqual(self.row()['status'], 'already_in_library')
        self.app.start_job.assert_not_called()

    def test_video_review_uses_jellyfin_and_discloses_move_policy(self):
        self.app.media_kind.return_value = 'movie'
        self.app.metadata_search.return_value = [dict(self.match, author='Movie', metadata={
            'kind':'movie', 'title':'Title', 'year':2024, 'provider_ids':{'Tmdb':'1'}, 'authors':[]})]
        row = self.prepare()
        self.assertEqual(row['media_kind'], 'movie')
        self.assertEqual(self.app.metadata_search.call_args.args[0]['kind'], 'movie')
        self.assertIn('removes verified source files', self.queue.content(row))
        self.vote(module.REJECT, {'456'})
        self.queue.tick()
        self.app.start_job.assert_not_called()
        self.assertEqual(self.row()['status'], 'rejected')

    def test_resolved_message_deleted_once_and_not_reposted_after_restart(self):
        self.prepare()
        self.queue.update(self.row()['id'], status='done', dirty=1)
        self.queue.tick()
        self.assertEqual(self.row()['discord_deleted'], 1)
        self.assertEqual(self.row()['message'], '789')
        self.discord.request.reset_mock()
        module.ReviewQueue(self.app, self.config, self.discord).tick()
        self.discord.request.assert_not_called()

    def test_delete_failure_retries_and_404_counts_as_success(self):
        self.prepare()
        self.queue.update(self.row()['id'], status='done')
        self.discord.request.side_effect = module.DiscordHTTPError(403)
        self.queue.tick()
        self.assertEqual(self.row()['discord_deleted'], 0)
        self.discord.request.side_effect = module.DiscordHTTPError(404)
        self.queue.tick()
        self.assertEqual(self.row()['discord_deleted'], 1)

    def test_resolution_cleanup_does_not_require_available_download_storage(self):
        self.prepare()
        self.queue.update(self.row()['id'], status='done')
        self.app.catalog.side_effect = ValueError('USB unavailable')
        with self.assertRaises(ValueError):
            self.queue.tick()
        self.assertEqual(self.row()['discord_deleted'], 1)

    def test_unresolved_failure_and_cleanup_keep_discord_message(self):
        self.prepare()
        for status in ('failed', 'interrupted', 'cleanup_required'):
            self.queue.update(self.row()['id'], status=status, dirty=0)
            self.discord.request.reset_mock()
            self.queue.tick()
            self.assertFalse(any(call.args[0] == 'DELETE' for call in self.discord.request.call_args_list))

    def test_removed_invalid_review_can_resolve_manually_without_reposting(self):
        self.prepare()
        key=self.row()['id']
        self.queue.update(key,status='needs_review',discord_deleted=1,dirty=0)
        module.manual_job(self.app,key,'Author - Title','manual2')
        with closing(self.app.database()) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?)',('manual2','Author - Title','done'))
            db.commit()
        self.discord.request.reset_mock()
        for _ in range(3):
            self.queue.tick()
        self.assertEqual(self.row()['status'],'done')
        self.discord.request.assert_not_called()

    def test_missing_approvers_fail_closed(self):
        with self.assertRaises(ValueError):
            module.ReviewQueue(self.app, dict(self.config, approver_ids=[]), self.discord)

    def test_review_http_routes_preserve_auth_and_serve_direct_link(self):
        self.prepare()
        self.vote(module.REJECT, {'456'})
        name = 'approval_http_importer'
        importer_spec = importlib.util.spec_from_file_location(
            name, ROOT / 'services/qbittorrent-m920/importer.py')
        importer = importlib.util.module_from_spec(importer_spec)
        with patch.dict(sys.modules, {name: importer, 'discord_approval': module}):
            importer_spec.loader.exec_module(importer)
            with patch.object(importer, 'STATE', self.root), patch.object(importer, 'DOWNLOADS', self.root):
                server = importer.ThreadingHTTPServer(('127.0.0.1', 0), importer.Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base = f'http://127.0.0.1:{server.server_port}'
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(base + '/imports/api/reviews')
                    self.assertEqual(error.exception.code, 403)
                    headers = {'X-Authentik-Email': 'owner@example.invalid',
                               'X-Authentik-Groups': 'torrent-users'}
                    for route in ('/imports/api/reviews', '/imports/api/reviews/' + self.row()['id'],
                                  '/imports/reviews/', '/imports/?review=' + self.row()['id']):
                        with urllib.request.urlopen(urllib.request.Request(base + route, headers=headers)) as response:
                            self.assertEqual(response.status, 200)
                            self.assertTrue(response.read())
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()


if __name__ == '__main__':
    unittest.main(verbosity=2)
