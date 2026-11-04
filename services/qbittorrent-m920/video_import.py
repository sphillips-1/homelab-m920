"""Approved movie/TV transfers to Jellyfin, with verified copies before source removal."""
from contextlib import closing
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import shutil
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

VIDEO = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.webm', '.ts', '.mpg', '.mpeg'}
SUBTITLE = {'.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx', '.sup'}
EPISODE = re.compile(r'(?i)S(\d{1,2})E(\d{1,3})(?!\d)')
MEDIA_ROOT = Path(os.getenv('IMPORT_VIDEO_ROOT', '/jellymedia'))


def api(route, data=None, method='GET'):
    token = os.getenv('JELLYFIN_API_KEY', '')
    if not token:
        raise ValueError('Jellyfin integration credential is unavailable.')
    request = urllib.request.Request(os.getenv('JELLYFIN_URL', 'http://jellyfin:8096').rstrip('/') + route,
        data=json.dumps(data).encode() if data is not None else None, method=method,
        headers={'X-Emby-Token': token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read()
        return json.loads(content) if content else None


def release_match(name):
    return next((m for m in re.finditer(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)', name)
                 if name[:m.start()].strip(' -_.([')), None)


def guess(source, files):
    videos = [p for p, _, _ in files if p.suffix.lower() in VIDEO]
    kind = 'tv' if any(EPISODE.search(p.stem) for p in videos) else 'movie'
    name = videos[0].stem if source.is_file() and videos else source.name
    if kind == 'tv':
        name = EPISODE.split(videos[0].stem)[0]
    year = release_match(name)
    if year:
        name = name[:year.start()]
    else:
        name = re.split(r'(?i)[. _-](?:2160p|1080p|720p|480p|bluray|web[- .]?dl|webrip|hdtv)\b', name)[0]
    return kind, re.sub(r'[._]+', ' ', name).strip(' -_([')


def ready(app):
    app.storage_ready()
    roots = [MEDIA_ROOT / name for name in ('movies', 'tv', '.jellyfin-imports')]
    if MEDIA_ROOT.is_symlink() or any(p.is_symlink() or not p.is_dir() for p in roots):
        raise ValueError('The Jellyfin library or staging mount is unavailable.')
    if any(p.stat().st_dev != app.LIBRARY.stat().st_dev for p in roots):
        raise ValueError('Jellyfin and audiobook libraries must be on the expected library drive.')


def safe_path(path, base=None):
    base = MEDIA_ROOT if base is None else base
    if not path.is_absolute() or '..' in path.parts or not path.is_relative_to(base) or path == base:
        raise ValueError('Invalid Jellyfin destination.')
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError('Symbolic links cannot be used for media transfers.')
        if part == base:
            break
    return path


def folder(app, metadata):
    title = app.component(re.sub(r'[:/\\]', ' - ', metadata['title']))
    year = metadata.get('year')
    if year:
        title += ' (' + str(int(year)) + ')'
    ids = metadata.get('provider_ids', {})
    for key in ('Tmdb', 'Imdb', 'Tvdb'):
        if ids.get(key):
            title += ' [' + key.lower() + 'id-' + ids[key] + ']'
            break
    return app.component(title)


def items(kind):
    result, start = [], 0
    while True:
        query = urllib.parse.urlencode({'Recursive': 'true', 'IncludeItemTypes': kind,
            'Fields': 'ProviderIds,Path', 'StartIndex': start, 'Limit': 200})
        page = api('/Items?' + query)
        rows = page.get('Items', [])
        result.extend(rows)
        start += len(rows)
        if not rows or start >= page.get('TotalRecordCount', start):
            return result


def matching(app, metadata):
    for item in items('Movie' if metadata['kind'] == 'movie' else 'Series'):
        ids = metadata.get('provider_ids', {})
        stored = item.get('ProviderIds', {})
        same_id = any(str(value).casefold() == str(stored.get(key, '')).casefold()
                      for key, value in ids.items() if value)
        same_name = app.identity_text(item.get('Name')) == app.identity_text(metadata['title'])
        same_year = bool(metadata.get('year')) and item.get('ProductionYear') == metadata['year']
        if same_id or (same_name and same_year):
            return item
    return None


def search(app, payload):
    kind = payload.get('kind')
    if kind not in ('movie', 'tv'):
        raise ValueError('Choose Movie or TV series.')
    title = app.component(payload.get('title'))
    query = {'Name': title}
    if payload.get('year'):
        query['Year'] = int(payload['year'])
    candidates = api('/Items/RemoteSearch/' + ('Movie' if kind == 'movie' else 'Series'),
                     {'SearchInfo': query}, 'POST')
    if not isinstance(candidates, list):
        raise ValueError('Jellyfin returned an invalid metadata response.')
    result = []
    with closing(app.database()) as db:
        for item in candidates[:12]:
            if not isinstance(item, dict) or not isinstance(item.get('Name'), str):
                continue
            ids = {key: str(value) for key, value in item.get('ProviderIds', {}).items()
                   if key in ('Tmdb', 'Imdb', 'Tvdb') and re.fullmatch(r'[A-Za-z0-9-]{1,50}', str(value))}
            canonical = item['Name'].strip()
            review_title = app.component(canonical.replace('/', ' - ').replace('\\', ' - '))
            metadata = {'kind': kind, 'title': canonical,
                        'year': item.get('ProductionYear'), 'provider_ids': ids,
                        'description': str(item.get('Overview') or '')[:10000], 'authors': []}
            if metadata['year'] is not None:
                metadata['year'] = int(metadata['year'])
            review = secrets.token_hex(16)
            author = 'Movie' if kind == 'movie' else 'TV series'
            db.execute('INSERT INTO reviews VALUES (?,?,?,?,?)',
                       (review, author, review_title, json.dumps(metadata), time.time() + 3600))
            result.append({'id': review, 'author': author, 'title': review_title,
                           'metadata': metadata, 'provider': 'Jellyfin'})
        db.commit()
    return result


def tv_destination(app, metadata, existing):
    if existing and existing.get('Path'):
        path = Path(existing['Path'])
        if not path.is_relative_to('/media/tv') or path == Path('/media/tv'):
            raise ValueError('The existing Jellyfin series is outside the managed TV library.')
        return safe_path(MEDIA_ROOT / 'tv' / path.relative_to('/media/tv'))
    return safe_path(MEDIA_ROOT / 'tv' / folder(app, metadata))


def plan(app, source, metadata):
    ready(app)
    files = app.source_files(source)
    videos = [p for p, _, _ in files if p.suffix.lower() in VIDEO]
    if not videos:
        raise ValueError('No video files found.')
    if any(p.suffix.lower() in app.AUDIO for p, _, _ in files):
        raise ValueError('Separate audio and video into individual completed-download folders.')
    existing = matching(app, metadata)
    name = folder(app, metadata)
    if metadata['kind'] == 'movie':
        if len(videos) != 1:
            raise ValueError('Place one movie per completed-download folder; split movie packs first.')
        target = safe_path(MEDIA_ROOT / 'movies' / name)
        if existing or target.exists():
            return target, []
        layout = [(videos[0], Path(name + videos[0].suffix.lower()))]
    else:
        target = tv_destination(app, metadata, existing)
        episodes = set()
        if existing:
            query = urllib.parse.urlencode({'Recursive': 'true', 'ParentId': existing['Id'],
                'IncludeItemTypes': 'Episode', 'Fields': 'Path', 'Limit': 100000})
            for episode in api('/Items?' + query).get('Items', []):
                if episode.get('ParentIndexNumber') is not None and episode.get('IndexNumber') is not None:
                    episodes.add((episode['ParentIndexNumber'], episode['IndexNumber']))
        layout, seen, prefixes = [], set(), set()
        for video in videos:
            match = EPISODE.search(video.stem)
            if not match or re.match(r'(?i)(?:E\d|-E?\d)', video.stem[match.end():]):
                raise ValueError('TV files need a single S01E01 episode code; split multi-episode videos first.')
            season, number = map(int, match.groups())
            prefixes.add(app.identity_text(video.stem[:match.start()]))
            if (season, number) in seen:
                raise ValueError('The download contains two files for the same TV episode.')
            seen.add((season, number))
            relative = Path(f'Season {season:02d}') / f'{name} - S{season:02d}E{number:02d}{video.suffix.lower()}'
            if (season, number) not in episodes and not (target / relative).exists():
                layout.append((video, relative))
        if len(prefixes) > 1:
            raise ValueError('Split different TV series into separate completed-download folders.')
    for video, relative in list(layout):
        for path, _, _ in files:
            if path.suffix.lower() in SUBTITLE and path.parent == video.parent and (
                    path.stem == video.stem or path.name.startswith(video.stem + '.')):
                ending = path.name[len(video.stem):]
                layout.append((path, relative.with_name(relative.stem + ending)))
    destinations = [str(relative).casefold() for _, relative in layout]
    if len(destinations) != len(set(destinations)):
        raise ValueError('Two source files would use the same Jellyfin filename.')
    return target, layout


def source_metadata(app, source):
    files = app.source_files(source)
    kind, title = guess(source, files)
    year_match = release_match(source.name)
    metadata = {'kind': kind, 'title': title, 'year': int(year_match[1]) if year_match else None,
                'provider_ids': {}}
    nfo = source / ('movie.nfo' if kind == 'movie' else 'tvshow.nfo') if source.is_dir() else None
    if nfo and nfo.is_file() and not nfo.is_symlink() and nfo.stat().st_size < 1048576:
        content = nfo.read_bytes()
        if b'<!DOCTYPE' not in content.upper() and b'<!ENTITY' not in content.upper():
            try:
                root = ET.fromstring(content)
                metadata['title'] = root.findtext('title') or title
                nfo_year = root.findtext('year')
                if nfo_year and nfo_year.isdigit():
                    metadata['year'] = int(nfo_year)
                for node in root.findall('uniqueid'):
                    key = {'tmdb':'Tmdb','imdb':'Imdb','tvdb':'Tvdb'}.get(node.get('type', '').lower())
                    if key and node.text and re.fullmatch(r'[A-Za-z0-9-]{1,50}', node.text):
                        metadata['provider_ids'][key] = node.text
            except ET.ParseError:
                pass
    # A bare title is insufficient; require provider identity or an explicit release year.
    return metadata if metadata['provider_ids'] or metadata['year'] else None


def existing(app, source, metadata=None):
    if metadata is None:
        metadata = source_metadata(app, source)
    if not metadata:
        return None
    target, layout = plan(app, source, metadata)
    return target.relative_to(MEDIA_ROOT).as_posix() if not layout else None


def torrent_command(action, hashes):
    if not hashes:
        return
    body = {'hashes': '|'.join(hashes)}
    if action == 'delete':
        body['deleteFiles'] = 'false'
    request = urllib.request.Request('http://127.0.0.1:8080/api/v2/torrents/' + action,
        data=urllib.parse.urlencode(body).encode(), headers={'Host': 'torrents.shelfgoblin.dev'}, method='POST')
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def owned_torrents(app, source):
    hashes = []
    for torrent in app.torrents():
        path = Path(torrent.get('content_path') or '/invalid')
        if path == source or path.is_relative_to(source) or source.is_relative_to(path):
            if source.is_relative_to(path) and source != path:
                raise ValueError('The selected source is only part of a larger torrent; move the complete torrent folder instead.')
            value = torrent.get('hash', '')
            if not re.fullmatch(r'[a-fA-F0-9]{40,64}', value):
                raise ValueError('The torrent identity is unavailable.')
            hashes.append(value)
    return sorted(hashes)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_nfo(path, metadata):
    root = ET.Element('movie' if metadata['kind'] == 'movie' else 'tvshow')
    ET.SubElement(root, 'title').text = metadata['title']
    if metadata.get('year'):
        ET.SubElement(root, 'year').text = str(metadata['year'])
    for key, value in metadata.get('provider_ids', {}).items():
        ET.SubElement(root, 'uniqueid', {'type': key.lower()}).text = value
    path.write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))


def save_transfer(app, job, manifest):
    with closing(app.database()) as db:
        db.execute('CREATE TABLE IF NOT EXISTS video_transfers (job TEXT PRIMARY KEY, manifest TEXT)')
        db.execute('INSERT OR REPLACE INTO video_transfers VALUES (?,?)', (job, json.dumps(manifest)))
        db.commit()


def finish_move(app, job):
    with closing(app.database()) as db:
        row = db.execute("SELECT status FROM jobs WHERE id=?", (job,)).fetchone()
        if not row or row['status'] != 'cleanup_required':
            raise ValueError('This transfer is not awaiting source cleanup.')
        transfer = db.execute('SELECT manifest FROM video_transfers WHERE job=?', (job,)).fetchone()
    if not row or row['status'] != 'cleanup_required' or not transfer:
        raise ValueError('This transfer is not awaiting source cleanup.')
    ready(app)
    manifest = json.loads(transfer['manifest'])
    source = Path(manifest['source'])
    safe_path(source, app.DOWNLOADS / 'complete')
    # Verify every published byte before any source deletion or torrent removal.
    for item in manifest['files']:
        target = safe_path(Path(item['target']))
        original = safe_path(Path(item['source']), app.DOWNLOADS / 'complete')
        if digest(target) != item['sha256']:
            raise ValueError('Published media changed; source files were preserved.')
        if original.exists() and (original.stat().st_size, original.stat().st_mtime_ns) != (item['size'], item['mtime']):
            raise ValueError('Download changed after approval; source files were preserved.')
    current = owned_torrents(app, source)
    if set(current) - set(manifest['torrents']):
        raise ValueError('Torrent ownership changed; source files were preserved.')
    torrent_command('stop', current)
    torrent_command('delete', current)  # Remove torrent record only; delete only verified files below.
    for item in manifest['files']:
        original = safe_path(Path(item['source']), app.DOWNLOADS / 'complete')
        if original.exists():
            if (original.stat().st_size, original.stat().st_mtime_ns) != (item['size'], item['mtime']):
                raise ValueError('Download changed during cleanup; remaining files were preserved.')
            original.unlink()
            if source.is_dir():
                parent = original.parent
                while parent.is_relative_to(source):
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    if parent == source:
                        break
                    parent = parent.parent
    app.update_job(job, 'done', 'Moved to Jellyfin. Seeding stopped; verified source video/subtitle files removed. Other extras remain on USB.')


def run_job(app, job, source, metadata):
    stage = MEDIA_ROOT / '.jellyfin-imports' / job
    published = []
    try:
        target, layout = plan(app, source, metadata)
        if not layout:
            raise ValueError('This media is already in the Jellyfin library.')
        hashes = owned_torrents(app, source)
        torrent_command('stop', hashes)
        snapshots = {p: (size, modified) for p, size, modified in app.source_files(source)}
        if shutil.disk_usage(MEDIA_ROOT).free < sum(snapshots[p][0] for p, _ in layout) + 512 * 1024 * 1024:
            raise ValueError('Not enough space on the Jellyfin library drive.')
        stage.mkdir(mode=0o750)
        manifest = {'source': str(source), 'torrents': hashes, 'files': []}
        for original, relative in layout:
            output = stage / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with os.fdopen(os.open(original, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as reader:
                before = os.fstat(reader.fileno())
                if (before.st_size, before.st_mtime_ns) != snapshots[original]:
                    raise ValueError('Download changed before copying.')
                with output.open('xb') as writer:
                    checksum = hashlib.sha256()
                    while block := reader.read(1024 * 1024):
                        checksum.update(block); writer.write(block)
                    writer.flush(); os.fsync(writer.fileno())
                after = os.fstat(reader.fileno())
                if (after.st_size, after.st_mtime_ns) != snapshots[original]:
                    raise ValueError('Download changed during copying.')
            os.chmod(output, 0o640)
            if digest(output) != checksum.hexdigest():
                raise ValueError('Copy verification failed; source files were preserved.')
            manifest['files'].append({'source': str(original), 'target': str(target / relative),
                'size': snapshots[original][0], 'mtime': snapshots[original][1], 'sha256': checksum.hexdigest()})
        ready(app)
        app.ensure_complete(source, app.torrents())
        if set(owned_torrents(app, source)) - set(hashes):
            raise ValueError('Torrent ownership changed before publishing.')
        nfo = 'movie.nfo' if metadata['kind'] == 'movie' else 'tvshow.nfo'
        write_nfo(stage / nfo, metadata)
        safe_path(target)
        if metadata['kind'] == 'movie':
            target.mkdir(mode=0o755)  # Exclusive reservation, including against empty destinations.
        else:
            target.mkdir(parents=True, exist_ok=True)
        # Publish approved metadata first, then complete, verified files with exclusive links.
        if not (target / nfo).exists():
            os.link(stage / nfo, target / nfo); published.append(target / nfo)
        for item in manifest['files']:
            destination = safe_path(Path(item['target']))
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.link(stage / destination.relative_to(target), destination)
            published.append(destination)
        save_transfer(app, job, manifest)
        app.update_job(job, 'cleanup_required', 'Published to Jellyfin. Finishing verified source cleanup…')
        try:
            api('/Library/Refresh', method='POST')
        except Exception:
            logging.warning('Jellyfin refresh unavailable for transfer %s; run Scan if needed', job)
        try:
            finish_move(app, job)
        except Exception as error:
            app.update_job(job, 'cleanup_required', 'Imported into Jellyfin; source cleanup needs review. ' +
                           (str(error) if isinstance(error, ValueError) else 'Check server logs and use Finish move.'))
            logging.warning('Jellyfin cleanup %s deferred (%s)', job, type(error).__name__)
    except Exception as error:
        # Only unpublished TV links created by this attempt are rolled back.
        for path in reversed(published):
            path.unlink(missing_ok=True)
        app.update_job(job, 'failed', str(error) if isinstance(error, ValueError)
                       else 'Video transfer failed; source files were preserved. Check server logs.')
        logging.warning('Jellyfin transfer %s failed (%s)', job, type(error).__name__)
    finally:
        try:
            if stage.exists():
                shutil.rmtree(stage)
        finally:
            app.lock.release()
