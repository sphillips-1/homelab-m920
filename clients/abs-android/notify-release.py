"""Send a confirmed APK publication to the private releases-mobile webhook."""
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def notify(env, send=urlopen):
    webhook = env.get('DISCORD_WEBHOOK', '').strip()
    if not re.fullmatch(r'https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+', webhook):
        raise ValueError('Configure DISCORD_RELEASES_MOBILE_WEBHOOK with the channel webhook URL.')
    base = f"{env['GITHUB_SERVER_URL']}/{env['GITHUB_REPOSITORY']}"
    build = env['GITHUB_RUN_NUMBER']
    tag = f'shelfgoblin-build-{build}'
    payload = {
        'username': 'ShelfGoblin releases',
        'allowed_mentions': {'parse': []},
        'content': (
            f'**ShelfGoblin Android build {build} published**\n'
            f'[Download APK]({base}/releases/download/{tag}/ShelfGoblin.apk)\n'
            f'[Release notes and source]({base}/releases/tag/{tag}) · '
            f"[Build]({base}/actions/runs/{env['GITHUB_RUN_ID']})\n"
            'Install over your existing ShelfGoblin app.'
        ),
    }
    request = Request(webhook + '?wait=true', data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json',
                               'User-Agent': 'ShelfGoblin-release-notifier/1.0'}, method='POST')
    # No automatic retries: an ambiguous timeout could otherwise duplicate a message.
    with send(request, timeout=30) as response:
        if response.status != 200 or not json.load(response).get('id'):
            raise ValueError('Discord did not confirm the release notification.')


if __name__ == '__main__':
    try:
        notify(os.environ)
    except (ValueError, KeyError, HTTPError, URLError, TimeoutError):
        # Exception text can contain the webhook token; never print it.
        print('::error::Release notification failed. Check the channel webhook secret and Discord availability.')
        sys.exit(1)
    print('Discord confirmed the mobile release notification.')
