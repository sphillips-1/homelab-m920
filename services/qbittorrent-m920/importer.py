#!/usr/bin/env python3
"""Owner-only audiobook copies from completed USB downloads into the library."""
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import stat
import threading
import time
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DOWNLOADS = Path(os.getenv('IMPORT_DOWNLOADS', '/downloads'))
LIBRARY = Path(os.getenv('IMPORT_LIBRARY', '/library'))
STAGING = Path(os.getenv('IMPORT_STAGING', '/staging'))
STATE = Path(os.getenv('IMPORT_STATE', '/state'))
ASSETS = Path(__file__).parent
USB_UUID = 'e440863e-34ce-4c29-b05a-c5dfda01a743'
AUDIO = {'.mp3', '.m4b', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.wav', '.wma'}
SUPPORT = {'.jpg', '.jpeg', '.png', '.webp', '.cue', '.txt', '.nfo', '.opf', '.json'}
lock = threading.Lock()

def database():
    db = sqlite3.connect(STATE / 'imports.sqlite')
    db.row_factory = sqlite3.Row
    return db

def initialize():
    STATE.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, source TEXT, '
                   'author TEXT, title TEXT, status TEXT, message TEXT, created REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, '
                   'author TEXT, title TEXT, metadata TEXT, expires REAL)')
        db.execute("UPDATE jobs SET status='interrupted', message=? WHERE status='copying'",
                   ('Import interrupted. Check the library before retrying.',))

def storage_ready():
    if (DOWNLOADS / '.homelab-torrent-volume').read_text().strip() != USB_UUID:
        raise ValueError('The torrent USB is unavailable.')
    if LIBRARY.stat().st_dev == STATE.stat().st_dev:
        raise ValueError('The audiobook library drive is unavailable.')
    if STAGING.stat().st_dev != LIBRARY.stat().st_dev:
        raise ValueError('The library staging drive is unavailable.')
    if DOWNLOADS.stat().st_dev == LIBRARY.stat().st_dev:
        raise ValueError('The torrent USB is unavailable.')
    if (DOWNLOADS / 'complete').is_symlink():
        raise ValueError('The completed download folder cannot be a symbolic link.')

def component(value):
    if not isinstance(value, str):
        raise ValueError('Enter an author and a book title.')
    value = value.strip()
    if (not value or value.startswith('.') or len(value) > 180
            or any(c in value for c in '/\\\x00') or any(ord(c) < 32 for c in value)):
        raise ValueError('Use a plain author or title without slashes.')
    return value

def source_files(source):
    if source.is_symlink():
        raise ValueError('Symbolic links cannot be imported.')
    paths = [source] if source.is_file() else sorted(source.rglob('*'))
    files = []
    for path in paths:
        if path.is_symlink():
            raise ValueError('Symbolic links cannot be imported.')
        info = path.stat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Only ordinary audio files can be imported.')
        if path.suffix.lower() in AUDIO | SUPPORT:
            files.append((path, info.st_size, info.st_mtime_ns))
    if not any(path.suffix.lower() in AUDIO for path, _, _ in files):
        raise ValueError('No audiobook audio files found. Extract archives first.')
    return files

def torrents():
    request = urllib.request.Request('http://127.0.0.1:8080/api/v2/torrents/info',
                                     headers={'Host': 'torrents.shelfgoblin.dev'})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)

def ensure_complete(source, current):
    for torrent in current:
        path = Path(torrent.get('content_path') or torrent.get('save_path') or '/invalid')
        if path == source or path.is_relative_to(source) or source.is_relative_to(path):
            state = torrent.get('state', '')
            if (torrent.get('progress', 0) < 1 or state.endswith('DL')
                    or state.startswith('checking') or state in ('error', 'missingFiles')):
                raise ValueError('This torrent is still downloading or being checked.')

def catalog():
    storage_ready()
    current = torrents()  # Fail closed if completion cannot be checked.
    result = []
    for source in sorted((DOWNLOADS / 'complete').iterdir()):
        if source.name.startswith('.'):
            continue
        try:
            ensure_complete(source, current)
            files = source_files(source)
        except ValueError:
            continue
        result.append({'source': source.name, 'title': source.stem if source.is_file()
                       else source.name, 'bytes': sum(size for _, size, _ in files)})
    return result

def destination(author, title):
    target = LIBRARY / component(author) / component(title)
    if target.parent.is_symlink() or target.is_symlink():
        raise ValueError('Library destination cannot be a symbolic link.')
    if target.exists():
        raise ValueError('This author/title already exists. Existing books are never overwritten.')
    return target

def scan_library():
    token = os.environ.get('AUDIOBOOKSHELF_API_TOKEN', '')
    if not token:
        raise ValueError('Imported. Run Scan in Audiobookshelf; automatic scan is unavailable.')
    base = os.getenv('AUDIOBOOKSHELF_URL', 'http://audiobookshelf:80').rstrip('/')
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
    with urllib.request.urlopen(urllib.request.Request(base + '/api/libraries',
                                headers=headers), timeout=15) as response:
        libraries = json.load(response)['libraries']
    library = next((item for item in libraries if any(
        folder['fullPath'].rstrip('/') in ('/audiobooks', '/audiobooks/Books')
        for folder in item.get('folders', []))), None)
    if not library:
        raise ValueError('Imported. Run Scan in Audiobookshelf; the library was not found.')
    with urllib.request.urlopen(urllib.request.Request(
        base + '/api/libraries/' + library['id'] + '/scan', data=b'{}',
        headers=headers, method='POST'), timeout=15) as response:
        response.read()

def update_job(job, status, message):
    with database() as db:
        db.execute('UPDATE jobs SET status=?, message=? WHERE id=?', (status, message, job))

def copy_book(source, target, stage, metadata=None):
    storage_ready()
    files = source_files(source)
    required = sum(size for _, size, _ in files)
    if shutil.disk_usage(STAGING).free < required + 512 * 1024 * 1024:
        raise ValueError('Not enough space on the audiobook library drive.')
    stage.mkdir(mode=0o750)
    try:
        for path, size, modified in files:
            relative = Path(path.name) if source.is_file() else path.relative_to(source)
            output = stage / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            # No-follow protects against a symlink swap while copying.
            with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as reader:
                before = os.fstat(reader.fileno())
                if (before.st_size, before.st_mtime_ns) != (size, modified):
                    raise ValueError('Download changed during import; retry when complete.')
                with output.open('xb') as writer:
                    shutil.copyfileobj(reader, writer, 1024 * 1024)
                    writer.flush()
                    os.fsync(writer.fileno())
                after = os.fstat(reader.fileno())
                if (after.st_size, after.st_mtime_ns) != (size, modified):
                    raise ValueError('Download changed during import; retry when complete.')
            os.chmod(output, 0o640)
        if metadata is not None:
            # Override only the copied sidecar; never change the USB original.
            sidecar = stage / 'metadata.json'
            try:
                existing = json.loads(sidecar.read_text(encoding='utf-8'))
                if not isinstance(existing, dict):
                    existing = {}
            except (OSError, ValueError):
                existing = {}
            legacy = existing.pop('metadata', None)
            if isinstance(legacy, dict):
                existing.update(legacy)
            existing.update(metadata)
            sidecar.write_text(json.dumps(existing, ensure_ascii=False),
                                                 encoding='utf-8')
        storage_ready()
        ensure_complete(source, torrents())
        target.parent.mkdir(mode=0o755, exist_ok=True)
        # Reserve the destination without replacing even an existing empty book.
        target.mkdir(mode=0o750)
        try:
            stage.rename(target)
        except Exception:
            target.rmdir()
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)

def run_job(job, source, target, metadata=None):
    try:
        copy_book(source, target, STAGING / job, metadata)
    except Exception as error:
        update_job(job, 'failed', str(error) if isinstance(error, ValueError)
                   else 'Import failed. Check server logs and library storage.')
    else:
        try:
            scan_library()
            message = 'Imported. Audiobookshelf scan requested; the USB copy is preserved.'
        except Exception:
            message = 'Imported. Open Audiobookshelf and run Scan to refresh the library.'
        update_job(job, 'done', message)
    finally:
        lock.release()

def metadata_search(payload):
    author, title = component(payload.get('author')), component(payload.get('title'))
    provider = payload.get('provider', 'audible')
    if provider not in ('audible', 'google', 'openlibrary'):
        raise ValueError('Choose a supported metadata provider.')
    token = os.environ.get('AUDIOBOOKSHELF_API_TOKEN', '')
    base = os.getenv('AUDIOBOOKSHELF_URL', 'http://audiobookshelf:80').rstrip('/')
    query = urllib.parse.urlencode({'title': title, 'author': author, 'provider': provider})
    request = urllib.request.Request(base + '/api/search/books?' + query,
                                     headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request, timeout=30) as response:
        candidates = json.load(response)
    if not isinstance(candidates, list):
        raise ValueError('ABS returned an invalid metadata response.')
    result = []
    with database() as db:
        db.execute('DELETE FROM reviews WHERE expires < ?', (time.time(),))
        for candidate in candidates[:12]:
            if (not isinstance(candidate.get('title'), str) or not candidate['title']
                    or not isinstance(candidate.get('author'), str) or not candidate['author']):
                continue
            metadata = {'title': candidate['title'], 'authors': [candidate['author']]}
            for field in ('subtitle', 'publisher', 'publishedYear', 'isbn', 'asin', 'language'):
                if candidate.get(field) is not None:
                    metadata[field] = str(candidate[field])
            metadata['description'] = str(candidate.get('descriptionPlain') or '')[:10000]
            for field in ('genres', 'tags'):
                if isinstance(candidate.get(field), list):
                    metadata[field] = [v for v in candidate[field] if isinstance(v, str)]
            if candidate.get('narrator'):
                metadata['narrators'] = [n.strip() for n in candidate['narrator'].split(',') if n.strip()]
            if isinstance(candidate.get('abridged'), bool):
                metadata['abridged'] = candidate['abridged']
            metadata['series'] = []
            series_values = candidate.get('series') or []
            if isinstance(series_values, str):
                series_values = [series_values]
            for series in series_values:
                if isinstance(series, dict) and series.get('series'):
                    sequence = str(series.get('sequence') or '')
                    metadata['series'].append(series['series'] + (' #' + sequence if sequence else ''))
                elif isinstance(series, str):
                    metadata['series'].append(series)
            folder_author = component(candidate['author'].replace('/', ' - ').replace('\\', ' - '))
            folder_title = component(candidate['title'].replace('/', ' - ').replace('\\', ' - '))
            review = secrets.token_hex(16)
            db.execute('INSERT INTO reviews VALUES (?, ?, ?, ?, ?)',
                       (review, folder_author, folder_title, json.dumps(metadata), time.time() + 3600))
            result.append({'id': review, 'author': folder_author, 'title': folder_title,
                           'metadata': metadata, 'provider': provider})
    return result

def reviewed_metadata(payload, author, title):
    if payload.get('manual') is True:
        return {'title': title, 'authors': [author]}
    with database() as db:
        review = db.execute('SELECT * FROM reviews WHERE id=? AND expires>?',
                            (payload.get('review', ''), time.time())).fetchone()
    if not review or (review['author'], review['title']) != (author, title):
        raise ValueError('Review an ABS match, or explicitly confirm manual metadata.')
    return json.loads(review['metadata'])

def start_job(payload):
    source_name = payload.get('source')
    available = {item['source'] for item in catalog()}
    if source_name not in available:
        raise ValueError('Choose a completed audiobook from the list.')
    author, title = component(payload.get('author')), component(payload.get('title'))
    metadata = reviewed_metadata(payload, author, title)
    target = destination(author, title)
    if not lock.acquire(blocking=False):
        raise ValueError('An import is already running. Wait for it to finish.')
    job = secrets.token_hex(16)
    try:
        with database() as db:
            db.execute('INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (job, source_name, author, title, 'copying', 'Copying audiobook…', time.time()))
        threading.Thread(target=run_job, args=(job, DOWNLOADS / 'complete' / source_name,
                                              target, metadata), daemon=True).start()
    except Exception:
        lock.release()
        raise
    return {'id': job}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, code, data, kind='application/json'):
        body = json.dumps(data).encode() if kind == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        return bool(self.headers.get('X-Authentik-Email')) and 'torrent-users' in (
            self.headers.get('X-Authentik-Groups', '').split('|'))

    def do_GET(self):
        if self.path == '/health':
            self.send(200, {'ok': True})
            return
        if not self.authorized():
            self.send(403, {'error': 'Sign in with your approved account.'})
            return
        try:
            if self.path == '/imports/api/downloads':
                self.send(200, catalog())
            elif self.path == '/imports/api/jobs':
                with database() as db:
                    rows = db.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 20').fetchall()
                self.send(200, [dict(row) for row in rows])
            elif self.path in ('/imports/', '/imports/app.js', '/imports/style.css'):
                filename = {'/imports/': 'import.html', '/imports/app.js': 'import.js',
                            '/imports/style.css': 'import.css'}[self.path]
                kind = {'import.html': 'text/html; charset=utf-8', 'import.js': 'text/javascript',
                        'import.css': 'text/css'}[filename]
                self.send(200, (ASSETS / filename).read_bytes(), kind)
            else:
                self.send(404, {'error': 'Not found'})
        except Exception as error:
            self.send(503, {'error': str(error) if isinstance(error, ValueError)
                           else 'Downloads or library storage are unavailable.'})

    def do_POST(self):
        if not self.authorized():
            self.send(403, {'error': 'Sign in with your approved account.'})
            return
        if (self.path not in ('/imports/api/import', '/imports/api/metadata') or
                self.headers.get('Origin') != 'https://torrents.shelfgoblin.dev' or
                self.headers.get('Content-Type') != 'application/json'):
            self.send(403, {'error': 'Invalid import request.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length < 8192:
                raise ValueError('Invalid request size.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Invalid import request.')
            if self.path == '/imports/api/metadata':
                self.send(200, metadata_search(payload))
            else:
                self.send(202, start_job(payload))
        except (ValueError, TypeError) as error:
            self.send(400, {'error': str(error)})
        except Exception:
            self.send(503, {'error': 'Downloads or library storage are unavailable.'})

if __name__ == '__main__':
    os.umask(0o027)
    initialize()
    ThreadingHTTPServer(('127.0.0.1', 8092), Handler).serve_forever()
