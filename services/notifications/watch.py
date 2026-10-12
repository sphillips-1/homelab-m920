"""Poll ABS for new audiobooks; persist a silent baseline and delivery progress."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

STATE = Path('/state/books.json')
INTERVAL = int(os.environ.get('POLL_INTERVAL', '60'))
SETTLE = int(os.environ.get('SETTLE_SECONDS', '300'))


def request(url, payload=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(url, headers=headers,
                  data=None if payload is None else json.dumps(payload).encode())
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def snapshot():
    base = os.environ.get('AUDIOBOOKSHELF_URL', 'http://audiobookshelf:80').rstrip('/')
    token = Path('/secrets/abs-token').read_text().strip()
    allowed = set(filter(None, os.environ.get('LIBRARY_IDS', '').split(',')))
    libraries = request(base + '/api/libraries', token=token)['libraries']
    books = {}
    for library in libraries:
        if library['mediaType'] != 'book' or (allowed and library['id'] not in allowed):
            continue
        page = 0
        while True:
            query = urlencode({'limit': 200, 'page': page, 'minified': 0})
            result = request(base + '/api/libraries/' + quote(library['id'], safe='') + '/items?' + query, token=token)
            items = result['results']
            for item in items:
                media = item['media']
                # Ignore ebook-only entries and incomplete audio scans.
                if not media.get('numAudioFiles', len(media.get('audioFiles', []))):
                    continue
                metadata = media['metadata']
                authors = metadata.get('authorName') or ', '.join(a['name'] for a in metadata.get('authors', []))
                books[item['id']] = {'title': metadata.get('title') or 'Untitled audiobook',
                                     'author': authors, 'library': library['name'],
                                     'size': media.get('size'), 'duration': media.get('duration'),
                                     'files': media.get('numAudioFiles', len(media.get('audioFiles', [])))}
            if (page + 1) * 200 >= result['total']:
                break
            if not items:
                raise ValueError('ABS returned an incomplete page')
            page += 1
    return books


def advance(state, books, now):
    if state is None:
        return {'version': 1, 'seen': sorted(books), 'pending': {}}
    if state.get('version') != 1 or not isinstance(state.get('seen'), list) or not isinstance(state.get('pending'), dict):
        raise ValueError('Invalid watcher state; refusing to reset the baseline')
    seen = set(state['seen'])
    pending = state['pending']
    for item_id in list(pending):
        if item_id not in books:
            del pending[item_id]
    for item_id, book in books.items():
        if item_id in seen:
            continue
        if item_id not in pending or pending[item_id]['book'] != book:
            pending[item_id] = {'book': book, 'stable_since': now}
    return state


def save(state):
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state))
    temporary.replace(STATE)


def notify(book, item_id=None, test=False):
    destination = Path('/secrets/apprise-url').read_text().strip()
    if item_id:
        destination += ('&' if '?' in destination else '?') + urlencode({
            'click': 'https://audiobooks.shelfgoblin.dev/item/' + quote(item_id, safe='')})
    result = request(os.environ.get('APPRISE_URL', 'http://apprise:8000/notify/'), {
        'urls': destination,
        'title': 'TEST: Shelf Goblin notifications' if test else 'New on Shelf Goblin',
        'body': book['title'] + ('\nby ' + book['author'] if book.get('author') else '') +
                '\n\n' + ('This is a delivery test.' if test else 'Now available in Audiobookshelf.'),
        'format': 'text'})
    if result.get('error') or result.get('status') not in (None, 'ok', 'success'):
        raise RuntimeError('Apprise rejected delivery')


def cycle():
    books = snapshot()  # Fetch every library successfully before changing state.
    state = json.loads(STATE.read_text()) if STATE.exists() else None
    first = state is None
    state = advance(state, books, time.time())
    save(state)
    if first:
        print(f'Silent baseline recorded: {len(books)} audiobooks.', flush=True)
    delivered = 0
    for item_id, pending in list(state['pending'].items()):
        if time.time() - pending['stable_since'] < SETTLE:
            continue
        notify(pending['book'], item_id)
        state['seen'].append(item_id)
        del state['pending'][item_id]
        save(state)  # Persist each success before sending the next message.
        delivered += 1
        if delivered >= 10:
            break
        time.sleep(1)
    Path('/state/heartbeat').touch()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.test:
        notify({'title': 'New-book notification delivery is working.', 'author': ''}, test=True)
    elif args.once:
        cycle()
    else:
        while True:
            try:
                cycle()
            except Exception as error:
                # HTTP errors can contain URLs, credentials or response bodies.
                print(f'Notification cycle failed ({type(error).__name__}); retrying.', flush=True)
            time.sleep(INTERVAL)
