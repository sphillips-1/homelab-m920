"""Receive private JSON on stdin inside the importer; invoked only by Actions."""
import json
import os
from pathlib import Path
import sys
import tempfile

from discord_approval import Discord, validate_config


def main():
    config = json.load(sys.stdin)
    validate_config(config)
    discord = Discord(config)
    if not discord.request('GET', '/users/@me').get('bot'):
        raise ValueError('A Discord bot token is required')
    discord.request('GET', '/channels/' + config['channel_id'])
    directory = Path(os.getenv('IMPORT_STATE', '/state'))
    fd, temporary = tempfile.mkstemp(prefix='.discord-approval-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(config, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, directory / 'discord-approval.secret')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Discord bot/channel verified; private approval configuration installed.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # JSON parser errors could contain credential text; do not print them.
        print('Discord approval configuration rejected; check private secret fields.', file=sys.stderr)
        sys.exit(1)
