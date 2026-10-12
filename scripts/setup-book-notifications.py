#!/usr/bin/env python3
"""Create private notification credentials once, preserving them on reruns."""
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path('/srv/homelab/appdata/notifications')
COMPOSE = ['docker', 'compose', '-f', '/opt/homelab/services/notifications/compose.yml']


def private_file(path, text):
    if not path.exists():
        with path.open('x') as stream:
            stream.write(text + '\n')
    path.chmod(0o600)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root.')
    for directory in ('ntfy', 'watcher', 'secrets'):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    (ROOT / 'secrets').chmod(0o700)
    # Obtain the existing automation token privately; never print container env.
    token_path = ROOT / 'secrets/abs-token'
    if not token_path.exists():
        data = json.loads(subprocess.check_output([
            'docker', 'inspect', 'authentik-invitation-provisioner']))
        env = dict(value.split('=', 1) for value in data[0]['Config']['Env'] if '=' in value)
        token = env.get('AUDIOBOOKSHELF_API_TOKEN')
        if not token:
            raise SystemExit('Existing ABS automation token is unavailable.')
        private_file(token_path, token)
    private_file(ROOT / 'secrets/publisher-password', secrets.token_hex(24))
    private_file(ROOT / 'secrets/family-password', secrets.token_hex(24))
    publisher = (ROOT / 'secrets/publisher-password').read_text().strip()
    private_file(ROOT / 'secrets/apprise-url',
                 f'ntfy://book-publisher:{publisher}@ntfy:80/new-books?tags=books')
    subprocess.run(COMPOSE + ['up', '-d', 'ntfy', 'apprise'], check=True)
    for username, filename, permission in (
            ('book-publisher', 'publisher-password', 'write-only'),
            ('family', 'family-password', 'read-only')):
        password = (ROOT / 'secrets' / filename).read_text().strip()
        env = dict(os.environ, NTFY_PASSWORD=password)
        subprocess.run(['docker', 'exec', '-e', 'NTFY_PASSWORD', 'homelab-ntfy',
                        'ntfy', 'user', 'add', '--ignore-exists', username], env=env, check=True)
        subprocess.run(['docker', 'exec', 'homelab-ntfy', 'ntfy', 'access', username,
                        'new-books', permission], check=True)
    subprocess.run(COMPOSE + ['up', '-d', 'book-notifications'], check=True)
    subprocess.run(COMPOSE + ['restart', 'book-notifications'], check=True)
    print('New-book watcher enabled. Phone credentials remain in notifications/secrets/family-password.')


if __name__ == '__main__':
    main()
