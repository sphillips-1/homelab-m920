"""Durable Discord reaction reviews, running inside the existing importer process."""
from contextlib import closing
import hashlib
import json
import logging
from pathlib import Path
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

CHOICES = ('1️⃣', '2️⃣', '3️⃣')
REJECT = '❌'
RESOLVED = ('done', 'already_in_library')


class DiscordHTTPError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__('Discord HTTP ' + str(status))


def validate_config(config):
    for field in ('channel_id', 'notify_user_id'):
        if not isinstance(config.get(field), str) or not config[field].isdigit():
            raise ValueError('Discord channel and notification user IDs are required')
    users = config.get('approver_ids')
    if not isinstance(users, list) or not users or any(
            not isinstance(user, str) or not user.isdigit() for user in users):
        raise ValueError('Explicit Discord approver IDs are required')
    if not isinstance(config.get('bot_token'), str) or not config['bot_token'].strip():
        raise ValueError('Discord bot token is required')


def reviews(app, key=None):
    path = app.STATE / 'discord-approvals.sqlite'
    if not path.is_file():
        if key:
            raise ValueError('Review not found.')
        return []
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        fields = 'id,source,status,matches,actor,seen,job,media_kind'
        if key:
            row = db.execute('SELECT ' + fields + ' FROM queue WHERE id=?', (key,)).fetchone()
            if not row:
                raise ValueError('Review not found.')
            result = dict(row)
            result['matches'] = json.loads(result['matches'] or '[]')
            app.component(result['source'])
            source = app.DOWNLOADS / 'complete' / result['source']
            result['files'] = [{'path': str(path.relative_to(source)) if source.is_dir() else path.name,
                                'bytes': size} for path, size, _ in app.source_files(source)]
            sidecar = source / 'metadata.json' if source.is_dir() else None
            result['sidecar'] = None
            if sidecar and not sidecar.is_symlink() and sidecar.is_file() and sidecar.stat().st_size < 1048576:
                try:
                    result['sidecar'] = json.loads(sidecar.read_text(encoding='utf-8'))
                except ValueError:
                    pass
            return result
        return [dict(row) for row in db.execute(
            "SELECT id,source,status,seen FROM queue WHERE status IN "
            "('rejected','needs_review','source_changed','failed','interrupted','cleanup_required') ORDER BY seen")]


def manual_job(app, key, source, job=None):
    """Bind a web import to its queue item without accepting a caller-supplied source."""
    with closing(sqlite3.connect(app.STATE / 'discord-approvals.sqlite')) as db:
        row = db.execute('SELECT source,status FROM queue WHERE id=?', (key,)).fetchone()
        if not row or row[0] != source or row[1] in ('starting', 'importing', 'done', 'already_in_library'):
            raise ValueError('This review is unavailable for import.')
        if job:
            db.execute("UPDATE queue SET status='importing',job=?,dirty=1 WHERE id=?", (job, key))
            db.commit()


class Discord:
    def __init__(self, config):
        self.config = config
        self.until = 0

    def request(self, method, route, data=None):
        delay = self.until - time.time()
        if delay > 5:
            raise RuntimeError('Discord rate limit cooldown')
        if delay > 0:
            time.sleep(delay)
        request = urllib.request.Request(
            'https://discord.com/api/v10' + route,
            data=json.dumps(data).encode() if data is not None else None,
            method=method, headers={
                'Authorization': 'Bot ' + self.config['bot_token'],
                'Content-Type': 'application/json',
                'User-Agent': 'HomelabAudiobookApproval/1.0'})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read()
                if response.headers.get('X-RateLimit-Remaining') == '0':
                    self.until = time.time() + float(response.headers.get('X-RateLimit-Reset-After', 1))
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            if error.code == 429:
                self.until = time.time() + float(json.loads(error.read()).get('retry_after', 30))
            # Never expose request headers or credentials in logs.
            raise DiscordHTTPError(error.code) from None

    def voters(self, route, emoji):
        result, after = set(), '0'
        while True:
            users = self.request('GET', route + '/reactions/' +
                                 urllib.parse.quote(emoji, safe='') + '?limit=100&after=' + after)
            result.update(user['id'] for user in users if not user.get('bot'))
            if len(users) < 100:
                return result
            after = users[-1]['id']


class ReviewQueue:
    def __init__(self, app, config, discord=None):
        self.app, self.config = app, config
        validate_config(config)
        self.discord = discord or Discord(config)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS queue ('
                       'id TEXT PRIMARY KEY, source TEXT UNIQUE, fingerprint TEXT, '
                       'seen REAL, status TEXT, matches TEXT, message TEXT, '
                       'selected INTEGER, actor TEXT, job TEXT, dirty INTEGER DEFAULT 1)')
            columns = {row[1] for row in db.execute('PRAGMA table_info(queue)')}
            if 'reply' not in columns:
                db.execute('ALTER TABLE queue ADD COLUMN reply TEXT')
            if 'library_path' not in columns:
                db.execute('ALTER TABLE queue ADD COLUMN library_path TEXT')
            if 'media_kind' not in columns:
                db.execute("ALTER TABLE queue ADD COLUMN media_kind TEXT DEFAULT 'audiobook'")
            if 'discord_deleted' not in columns:
                db.execute('ALTER TABLE queue ADD COLUMN discord_deleted INTEGER NOT NULL DEFAULT 0')
            # A crash between job creation and queue association must never retry a copy.
            db.execute("UPDATE queue SET status='needs_review', dirty=1 WHERE status='starting'")
            db.commit()

    def db(self):
        connection = sqlite3.connect(self.app.STATE / 'discord-approvals.sqlite')
        connection.row_factory = sqlite3.Row
        return closing(connection)

    def update(self, key, **values):
        with self.db() as db:
            db.execute('UPDATE queue SET ' + ','.join(name + '=?' for name in values) +
                       ' WHERE id=?', (*values.values(), key))
            db.commit()

    def fingerprint(self, source):
        files = self.app.source_files(self.app.DOWNLOADS / 'complete' / source)
        return hashlib.sha256(json.dumps([(str(path), size, modified)
                              for path, size, modified in files]).encode()).hexdigest()

    def discover(self):
        # catalog validates storage, audio files and qBittorrent completion.
        available = self.app.catalog()
        for item in available:
            fingerprint = self.fingerprint(item['source'])
            with self.db() as db:
                row = db.execute('SELECT * FROM queue WHERE source=?', (item['source'],)).fetchone()
                if not row:
                    db.execute('INSERT INTO queue (id,source,fingerprint,seen,status) VALUES (?,?,?,?,?)',
                               (secrets.token_hex(12), item['source'], fingerprint, time.time(), 'settling'))
                    db.commit()
                elif row['status'] == 'settling' and row['fingerprint'] != fingerprint:
                    self.update(row['id'], fingerprint=fingerprint, seen=time.time())
        return {item['source'] for item in available}

    def gather(self, row):
        source = self.app.DOWNLOADS / 'complete' / row['source']
        kind = self.app.media_kind(source)
        if kind != 'audiobook':
            matches = self.app.metadata_search({'kind': kind, 'title': self.app.media_name(source), 'year': self.app.media_year(source)})[:3]
            self.update(row['id'], media_kind=kind, matches=json.dumps(matches), status='pending', dirty=1)
            return
        author, title = '', source.stem if source.is_file() else source.name
        sidecar = source / 'metadata.json' if source.is_dir() else None
        if sidecar and sidecar.is_file() and not sidecar.is_symlink() and sidecar.stat().st_size < 1048576:
            try:
                data = json.loads(sidecar.read_text(encoding='utf-8'))
                data = data.get('metadata', data)
                authors = data.get('authors', [])
                author = ', '.join(authors) if isinstance(authors, list) else ''
                title = data.get('title') or title
            except (ValueError, TypeError, AttributeError):
                pass
        identity = self.app.source_identity(source)
        if identity.get('title') and identity.get('authors'):
            author = ', '.join(identity['authors'])
            title = identity['title']
        if not author and ' - ' in title:
            author, title = title.split(' - ', 1)
        matches = self.app.metadata_search({'author': author, 'title': title,
                                            'provider': 'audible'})[:3]
        # Persist full candidates; one-hour web review tokens are not used for Discord.
        self.update(row['id'], matches=json.dumps(matches), status='pending', dirty=1)

    def content(self, row):
        lines = [f"<@{self.config['notify_user_id']}> Media review `{row['id']}`",
                 'Download: ' + row['source'][:200]]
        for emoji, match in zip(CHOICES, json.loads(row['matches'] or '[]')):
            meta = match['metadata']
            detail = ('Jellyfin · ' + str(meta.get('year') or 'Year not supplied') + ' | ' + str(meta.get('provider_ids', {}))) if meta.get('kind') in ('movie', 'tv') else ' | '.join(filter(None, [', '.join(meta.get('narrators', [])),
                       ', '.join(meta.get('series', [])), meta.get('publishedYear'),
                       meta.get('publisher'), meta.get('language'), meta.get('asin'),
                       'Abridged' if meta.get('abridged') else
                       'Unabridged' if meta.get('abridged') is False else '']))
            lines.append(f"{emoji} {match['author']} — {match['title']}\n{detail}"[:430])
        if row['media_kind'] in ('movie', 'tv'):
            lines.append('Approval moves video/subtitles to Jellyfin, stops seeding and removes verified source files. Rejection keeps the source unchanged.')
        if row['status'] == 'pending':
            lines.append('React with a number to APPROVE that edition, or ❌ to REJECT. '
                         'One choice only; conflicting votes stay pending.')
            if not json.loads(row['matches'] or '[]'):
                lines.append('No usable metadata match. Review manually on the import page; only rejection is available here.')
        else:
            if row['status'] == 'already_in_library':
                lines.append('Already in the media library: ' + row['library_path'] + '. No import needed.')
            lines.append('Status: ' + row['status'] +
                         (' | decided by ' + row['actor'] if row['actor'] else ''))
            if row['job']:
                with closing(self.app.database()) as db:
                    job = db.execute('SELECT * FROM jobs WHERE id=?', (row['job'],)).fetchone()
                if job and 'message' in job.keys():
                    lines.append(job['message'][:250])
        lines.append('https://torrents.shelfgoblin.dev/imports/')
        return '\n'.join(lines)[:2000]

    def delete_resolved(self, row):
        if row['discord_deleted']:
            return
        route = '/channels/' + self.config['channel_id'] + '/messages/'
        # Keep IDs as audit history. A crash or partial failure safely retries already-deleted IDs.
        for field in ('reply', 'message'):
            if row[field]:
                try:
                    self.discord.request('DELETE', route + row[field])
                except DiscordHTTPError as error:
                    if error.status != 404:
                        raise
        self.update(row['id'], discord_deleted=1, dirty=0)

    def publish(self, row):
        if row['discord_deleted']:
            self.update(row['id'], dirty=0)
            return
        if row['status'] in RESOLVED:
            self.delete_resolved(row)
            return
        route = '/channels/' + self.config['channel_id'] + '/messages'
        data = {'content': self.content(row), 'allowed_mentions': {
            'parse': [], 'users': [self.config['notify_user_id']] if not row['message'] else []}}
        if not row['message']:
            data.update(nonce=row['id'], enforce_nonce=True)
            message = self.discord.request('POST', route, data)
            self.update(row['id'], message=message['id'])
            row = dict(row, message=message['id'])
        else:
            self.discord.request('PATCH', route + '/' + row['message'], data)
        if row['status'] == 'pending':
            for emoji in (*CHOICES[:len(json.loads(row['matches'] or '[]'))], REJECT):
                self.discord.request('PUT', route + '/' + row['message'] + '/reactions/' +
                                     urllib.parse.quote(emoji, safe='') + '/@me')
        self.update(row['id'], dirty=0)

    def decide(self, row):
        route = '/channels/' + self.config['channel_id'] + '/messages/' + row['message']
        votes = []
        matches = json.loads(row['matches'] or '[]')
        for index, emoji in [*enumerate(CHOICES[:len(matches)]), (-1, REJECT)]:
            actors = self.discord.voters(route, emoji) & set(self.config['approver_ids'])
            if actors:
                votes.append((index, sorted(actors)[0]))
        if len(votes) != 1:
            return
        index, actor = votes[0]
        with self.db() as db:
            db.execute('UPDATE queue SET selected=?,actor=?,status=?,dirty=1 '
                       "WHERE id=? AND status='pending'",
                       (index, actor, 'rejected' if index == -1 else 'approved', row['id']))
            db.commit()

    def rejected_reply(self, row):
        message = self.discord.request('POST', '/channels/' + self.config['channel_id'] + '/messages', {
            'content': 'Rejected metadata — queued for manual validation. Source files are unchanged.\n'
                       'https://torrents.shelfgoblin.dev/imports/?review=' + row['id'],
            'message_reference': {'message_id': row['message'], 'fail_if_not_exists': False},
            'allowed_mentions': {'parse': [], 'replied_user': False},
            'nonce': row['id'] + 'r', 'enforce_nonce': True})
        self.update(row['id'], reply=message['id'])

    def import_approved(self, row):
        if self.app.lock.locked():
            return
        available = {item['source'] for item in self.app.catalog()}
        if row['source'] not in available or self.fingerprint(row['source']) != row['fingerprint']:
            self.update(row['id'], status='source_changed', dirty=1)
            return
        # Do not retry previously started imports, including failed/interrupted web imports.
        with closing(self.app.database()) as db:
            previous = db.execute('SELECT id FROM jobs WHERE source=?', (row['source'],)).fetchone()
        if previous:
            self.update(row['id'], status='needs_review', dirty=1)
            return
        match = json.loads(row['matches'])[row['selected']]
        duplicate = self.app.existing_book(self.app.DOWNLOADS / 'complete' / row['source'], match['metadata'])
        if duplicate:
            self.update(row['id'], status='already_in_library', library_path=duplicate, dirty=bool(row['message']))
            return
        self.update(row['id'], status='starting', dirty=1)
        try:
            # Mint a fresh server-side review for the exact stored candidate.
            review = secrets.token_hex(16)
            with closing(self.app.database()) as db:
                db.execute('INSERT INTO reviews VALUES (?,?,?,?,?)',
                           (review, match['author'], match['title'],
                            json.dumps(match['metadata']), time.time() + 60))
                db.commit()
            job = self.app.start_job({'source': row['source'], 'author': match['author'],
                                      'title': match['title'], 'review': review, 'kind': match['metadata'].get('kind', 'audiobook')})
            self.update(row['id'], status='importing', job=job['id'], dirty=1)
        except Exception:
            self.update(row['id'], status='needs_review', dirty=1)
            raise

    def tick(self):
        # Resolution cleanup must work even if USB/storage discovery is unavailable.
        with self.db() as db:
            resolved = db.execute("SELECT * FROM queue WHERE status IN ('done','already_in_library') AND discord_deleted=0").fetchall()
        for row in resolved:
            try:
                self.delete_resolved(row)
            except Exception as error:
                logging.warning('Discord cleanup %s deferred (%s)', row['id'], type(error).__name__)
        available = self.discover()
        with self.db() as db:
            rows = db.execute('SELECT * FROM queue ORDER BY seen').fetchall()
        for row in rows:
            try:
                if row['status'] in ('settling', 'pending', 'rejected', 'approved', 'needs_review',
                                     'source_changed', 'failed', 'interrupted'):
                    if row['status'] != 'settling' or time.time() - row['seen'] >= 120:
                        duplicate = self.app.existing_book(self.app.DOWNLOADS / 'complete' / row['source'])
                        if duplicate:
                            self.update(row['id'], status='already_in_library', library_path=duplicate,
                                        dirty=bool(row['message']))
                            continue
                if row['status'] in RESOLVED:
                    continue
                if row['status'] == 'settling':
                    if row['source'] in available and time.time() - row['seen'] >= 120:
                        self.gather(row)
                elif row['selected'] == -1 and not row['reply'] and row['message'] and not row['discord_deleted']:
                    self.rejected_reply(row)
                elif row['dirty'] or not row['message']:
                    self.publish(row)
                elif row['status'] == 'pending':
                    self.decide(row)
                elif row['status'] == 'approved':
                    self.import_approved(row)
                elif row['status'] in ('importing', 'cleanup_required'):
                    with closing(self.app.database()) as db:
                        job = db.execute('SELECT * FROM jobs WHERE id=?', (row['job'],)).fetchone()
                    if job and job['status'] != 'copying' and job['status'] != row['status']:
                        self.update(row['id'], status=job['status'], dirty=1)
                        if job['status'] in RESOLVED:
                            self.delete_resolved(dict(row, status=job['status']))
            except Exception as error:
                logging.warning('Discord review %s deferred (%s)', row['id'], type(error).__name__)


def run(app):
    config_file = app.STATE / 'discord-approval.secret'
    if not config_file.is_file():
        logging.warning('Discord audiobook approval disabled: private configuration is absent')
        return
    try:
        queue = ReviewQueue(app, json.loads(config_file.read_text(encoding='utf-8')))
    except Exception as error:
        logging.error('Discord approval configuration invalid (%s)', type(error).__name__)
        return
    while True:
        try:
            queue.tick()
        except Exception as error:
            logging.warning('Discord review discovery deferred (%s)', type(error).__name__)
        time.sleep(30)
