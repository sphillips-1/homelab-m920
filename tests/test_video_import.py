"""Offline Jellyfin transfer tests use disposable media and mocked remote APIs."""
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import types
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / 'services/qbittorrent-m920'
sys.path.insert(0, str(SERVICE))
import video_import as video
spec = importlib.util.spec_from_file_location('video_test_importer', SERVICE / 'importer.py')
app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
spec.loader.exec_module(app)


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.downloads = self.root / 'downloads'
        self.complete = self.downloads / 'complete'
        self.complete.mkdir(parents=True)
        self.media = self.root / 'media'
        for name in ('movies', 'tv', '.jellyfin-imports', 'audiobooks', 'state'):
            (self.media / name).mkdir(parents=True)
        self.source = self.complete / 'Example.Movie.2024.1080p.mkv'
        self.source.write_bytes(b'fixture video')
        self.metadata = {'kind': 'movie', 'title': 'Example Movie', 'year': 2024,
                         'provider_ids': {'Tmdb': '123'}, 'authors': []}
        def database():
            db = sqlite3.connect(self.media / 'state/imports.sqlite', factory=ClosingConnection)
            db.row_factory = sqlite3.Row
            return db
        changes = [(app,'LIBRARY', self.media / 'audiobooks'), (app,'DOWNLOADS',self.downloads),
            (app,'STATE',self.media / 'state'), (app,'database',database),
            (app,'storage_ready',Mock()), (app,'torrents',Mock(return_value=[])),
            (video,'MEDIA_ROOT',self.media), (video,'matching',Mock(return_value=None)),
            (video,'api',Mock(return_value={'Items': [], 'TotalRecordCount':0})),
            (video,'torrent_command',Mock())]
        for obj, name, value in changes:
            p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        if not hasattr(os,'O_NOFOLLOW'):
            p=patch.object(os,'O_NOFOLLOW',0,create=True);p.start();self.addCleanup(p.stop)
        app.initialize()

    def job(self):
        with closing(app.database()) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',
                ('job1',self.source.name,'Movie','Example Movie','copying','Copying',0))
            db.commit()
        app.lock.acquire()
        video.run_job(app,'job1',self.source,self.metadata)
        with closing(app.database()) as db:
            return dict(db.execute('SELECT * FROM jobs WHERE id=?',('job1',)).fetchone())

    def test_movie_is_verified_published_and_then_source_removed(self):
        def command(action, hashes):
            if action == 'delete':
                self.assertTrue(self.source.exists())
                self.assertTrue(list((self.media/'movies').rglob('*.mkv')))
        video.torrent_command.side_effect=command
        app.torrents.return_value=[{'content_path':str(self.source),'hash':'a'*40,'progress':1,'state':'stoppedUP'}]
        row=self.job()
        self.assertEqual(row['status'],'done')
        self.assertFalse(self.source.exists())
        self.assertEqual(next((self.media/'movies').rglob('*.mkv')).read_bytes(),b'fixture video')
        self.assertTrue(next((self.media/'movies').rglob('movie.nfo')).exists())
        video.torrent_command.assert_any_call('delete',['a'*40])
        self.assertFalse(app.lock.locked())

    def test_copy_failure_preserves_source_and_does_not_delete_torrent(self):
        with patch.object(video,'digest',return_value='wrong checksum'):
            row=self.job()
        self.assertEqual(row['status'],'failed')
        self.assertTrue(self.source.exists())
        self.assertFalse(list((self.media/'movies').rglob('*.mkv')))
        self.assertFalse(any(call.args[0]=='delete' for call in video.torrent_command.call_args_list))

    def test_existing_movie_blocks_copy_and_preserves_source(self):
        video.matching.return_value={'Id':'existing'}
        row=self.job()
        self.assertEqual(row['status'],'failed')
        self.assertTrue(self.source.exists())
        video.torrent_command.assert_not_called()

    def test_cleanup_failure_keeps_published_media_and_can_retry(self):
        video.torrent_command.side_effect=lambda action,hashes: (_ for _ in ()).throw(OSError()) if action=='delete' else None
        row=self.job()
        self.assertEqual(row['status'],'cleanup_required')
        self.assertTrue(self.source.exists())
        self.assertTrue(list((self.media/'movies').rglob('*.mkv')))
        video.torrent_command.side_effect=None
        video.finish_move(app,'job1')
        self.assertFalse(self.source.exists())
        with closing(app.database()) as db:
            self.assertEqual(db.execute('SELECT status FROM jobs').fetchone()[0],'done')

    def test_changed_source_refuses_cleanup(self):
        video.torrent_command.side_effect=lambda action,hashes: (_ for _ in ()).throw(OSError()) if action=='delete' else None
        self.job()
        self.source.write_bytes(b'new source content')
        video.torrent_command.side_effect=None
        with self.assertRaisesRegex(ValueError,'Download changed'):
            video.finish_move(app,'job1')
        self.assertTrue(self.source.exists())
        self.assertTrue(list((self.media/'movies').rglob('*.mkv')))

    def test_changed_destination_refuses_source_cleanup(self):
        video.torrent_command.side_effect=lambda action,hashes: (_ for _ in ()).throw(OSError()) if action=='delete' else None
        self.job()
        next((self.media/'movies').rglob('*.mkv')).write_bytes(b'changed destination')
        video.torrent_command.side_effect=None
        with self.assertRaisesRegex(ValueError,'Published media changed'):
            video.finish_move(app,'job1')
        self.assertTrue(self.source.exists())

    def test_subtitles_move_and_unrelated_extras_remain(self):
        self.source.unlink()
        self.source=self.complete/'Movie';self.source.mkdir()
        (self.source/'film.mkv').write_bytes(b'movie')
        (self.source/'film.en.srt').write_bytes(b'subtitle')
        (self.source/'extra.txt').write_bytes(b'keep extra')
        self.assertEqual(self.job()['status'],'done')
        self.assertFalse((self.source/'film.mkv').exists())
        self.assertFalse((self.source/'film.en.srt').exists())
        self.assertTrue((self.source/'extra.txt').exists())
        self.assertEqual(next((self.media/'movies').rglob('*.srt')).read_bytes(),b'subtitle')

    def test_tv_episode_adds_to_existing_series_without_overwrite(self):
        self.source.unlink();self.source=self.complete/'Show.S01E02.mkv';self.source.write_bytes(b'episode2')
        self.metadata={'kind':'tv','title':'Show','year':2020,'provider_ids':{'Tmdb':'9'}}
        target=self.media/'tv/Existing Show/Season 01';target.mkdir(parents=True)
        existing=target/'old-S01E01.mkv';existing.write_bytes(b'episode1')
        video.matching.return_value={'Id':'series','Path':'/media/tv/Existing Show'}
        video.api.return_value={'Items':[{'ParentIndexNumber':1,'IndexNumber':1}]}
        self.assertEqual(self.job()['status'],'done')
        self.assertEqual(existing.read_bytes(),b'episode1')
        self.assertEqual(len(list(target.glob('*.mkv'))),2)
        self.assertFalse(self.source.exists())

    def test_tv_existing_episode_is_a_duplicate(self):
        self.source.unlink();self.source=self.complete/'Show.S01E01.mkv';self.source.write_bytes(b'episode')
        metadata={'kind':'tv','title':'Show','year':2020,'provider_ids':{}}
        video.matching.return_value={'Id':'series','Path':'/media/tv/Show'}
        video.api.return_value={'Items':[{'ParentIndexNumber':1,'IndexNumber':1}]}
        self.assertEqual(video.existing(app,self.source,metadata),'tv/Show')

    def test_movie_pack_and_ambiguous_tv_are_refused(self):
        source=self.complete/'Pack';source.mkdir()
        (source/'a.mkv').write_bytes(b'a');(source/'b.mkv').write_bytes(b'b')
        with self.assertRaisesRegex(ValueError,'one movie'):
            video.plan(app,source,self.metadata)
        metadata=dict(self.metadata,kind='tv')
        with self.assertRaisesRegex(ValueError,'episode code'):
            video.plan(app,source,metadata)

    def test_parent_torrent_is_not_stopped_for_a_partial_selection(self):
        app.torrents.return_value=[{'content_path':str(self.complete),'hash':'b'*40}]
        with self.assertRaisesRegex(ValueError,'part of a larger torrent'):
            video.owned_torrents(app,self.source)
        video.torrent_command.assert_not_called()

    def test_filename_detection_and_search_preview(self):
        self.assertEqual(app.media_kind(self.source),'movie')
        self.assertEqual(video.guess(self.source,app.source_files(self.source)),('movie','Example Movie'))
        video.api.return_value=[{'Name':'Example Movie','ProductionYear':2024,'ProviderIds':{'Tmdb':'123'}}]
        matches=video.search(app,{'kind':'movie','title':'Example Movie'})
        self.assertEqual(matches[0]['metadata']['kind'],'movie')
        self.assertEqual(matches[0]['metadata']['provider_ids'],{'Tmdb':'123'})
        self.assertTrue(self.source.exists())
        self.assertFalse(list((self.media/'movies').rglob('*.mkv')))

    def test_authenticated_import_job_dispatch_moves_video_not_audiobook(self):
        def thread_factory(target, args, daemon):
            return types.SimpleNamespace(start=lambda: target(*args))
        with patch.object(app.threading, 'Thread', side_effect=thread_factory):
            result = app.start_job({'source':self.source.name,'kind':'movie',
                'title':'Example Movie','year':2024,'manual':True,'author':''})
        with closing(app.database()) as db:
            job = db.execute('SELECT * FROM jobs WHERE id=?',(result['id'],)).fetchone()
        self.assertEqual(job['status'],'done')
        self.assertEqual(job['author'],'Movie')
        self.assertFalse(self.source.exists())

    def test_tv_pack_moves_only_missing_episodes(self):
        self.source.unlink(); self.source=self.complete/'Show'; self.source.mkdir()
        (self.source/'Show.S01E01.mkv').write_bytes(b'already cataloged source')
        (self.source/'Show.S01E02.mkv').write_bytes(b'new episode')
        self.metadata={'kind':'tv','title':'Show','year':2020,'provider_ids':{}}
        video.matching.return_value={'Id':'series','Path':'/media/tv/Show'}
        video.api.return_value={'Items':[{'ParentIndexNumber':1,'IndexNumber':1}]}
        self.assertEqual(self.job()['status'],'done')
        self.assertTrue((self.source/'Show.S01E01.mkv').exists())
        self.assertFalse((self.source/'Show.S01E02.mkv').exists())

    def test_publication_race_does_not_overwrite_existing_destination(self):
        original_write=video.write_nfo
        target=self.media/'movies'/video.folder(app,self.metadata)
        def competing_target(path, metadata):
            original_write(path, metadata)
            target.mkdir()
            (target/'keep.txt').write_bytes(b'preserve')
        with patch.object(video,'write_nfo',side_effect=competing_target):
            self.assertEqual(self.job()['status'],'failed')
        self.assertEqual((target/'keep.txt').read_bytes(),b'preserve')
        self.assertTrue(self.source.exists())
        self.assertFalse(any(call.args[0]=='delete' for call in video.torrent_command.call_args_list))

    def test_numeric_movie_title_is_not_mistaken_for_release_year(self):
        source = self.complete/'1917.2019.1080p.mkv'
        source.write_bytes(b'fixture')
        self.assertEqual(video.guess(source,app.source_files(source)),('movie','1917'))
        self.assertEqual(app.media_year(source),2019)

    def test_slash_in_provider_title_is_preserved_in_metadata(self):
        video.api.return_value=[{'Name':'Face/Off','ProductionYear':1997,'ProviderIds':{'Tmdb':'754'}}]
        match=video.search(app,{'kind':'movie','title':'Face Off'})[0]
        self.assertEqual(match['metadata']['title'],'Face/Off')
        self.assertEqual(match['title'],'Face - Off')

    def test_known_title_and_year_duplicate_is_hidden_before_review(self):
        video.matching.return_value={'Id':'existing'}
        self.assertIsNotNone(video.existing(app,self.source))
        self.assertTrue(self.source.exists())
        video.torrent_command.assert_not_called()

    def test_unknown_title_alone_is_not_silently_suppressed(self):
        source=self.complete/'Example Movie.mkv';source.write_bytes(b'fixture')
        video.matching.return_value={'Id':'existing'}
        self.assertIsNone(video.existing(app,source))

    def test_source_nfo_provider_id_allows_duplicate_detection(self):
        source=self.complete/'Unknown download';source.mkdir()
        (source/'film.mkv').write_bytes(b'fixture')
        (source/'movie.nfo').write_text('<movie><title>Example Movie</title><uniqueid type="tmdb">123</uniqueid></movie>')
        video.matching.return_value={'Id':'existing'}
        self.assertIsNotNone(video.existing(app,source))
        self.assertEqual(video.matching.call_args.args[1]['provider_ids'],{'Tmdb':'123'})

    def test_jellyfin_lookup_outage_does_not_block_download_catalog(self):
        video.matching.side_effect=OSError('offline')
        self.assertEqual(app.catalog()[0]['source'],self.source.name)
        self.assertTrue(self.source.exists())
        video.torrent_command.assert_not_called()

    def test_path_traversal_is_refused(self):
        with self.assertRaises(ValueError):
            video.safe_path(self.media/'movies/../../outside')

    def test_jellyfin_outage_preserves_source(self):
        video.matching.side_effect=OSError('offline')
        self.assertEqual(self.job()['status'],'failed')
        self.assertTrue(self.source.exists())
        video.torrent_command.assert_not_called()


if __name__=='__main__':
    unittest.main(verbosity=2)
