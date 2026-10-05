#!/usr/bin/env python3
"""Run on the M920 while qBittorrent is stopped; preserve unrelated settings."""
import configparser
from pathlib import Path
import os

root = Path('/srv/homelab')
config_dir = root / 'appdata/qbittorrent-m920/qBittorrent'
config_dir.mkdir(parents=True, exist_ok=True)
path = config_dir / 'qBittorrent.conf'
config = configparser.ConfigParser(interpolation=None, strict=False)
config.optionxform = str
config.read(path)
settings = {
    'Preferences': {
        'WebUI\\Address': '127.0.0.1',
        'WebUI\\Port': '8080',
        'WebUI\\LocalHostAuth': 'false',
        'WebUI\\AuthSubnetWhitelistEnabled': 'false',
        'WebUI\\CSRFProtection': 'true',
        'WebUI\\HostHeaderValidation': 'true',
        'WebUI\\ServerDomains': 'torrents.shelfgoblin.dev',
        'WebUI\\ReverseProxySupportEnabled': 'false',
        'Connection\\UPnP': 'false',
    },
    'BitTorrent': {
        'Session\\DefaultSavePath': '/downloads/complete',
        'Session\\TempPath': '/downloads/incomplete',
        'Session\\TempPathEnabled': 'true',
        'Session\\Port': '6881',
        'Session\\UseUPnP': 'false',
    },
}
for section, values in settings.items():
    if not config.has_section(section):
        config.add_section(section)
    for key, value in values.items():
        config.set(section, key, value)
temporary = path.with_suffix('.tmp')
with temporary.open('w') as stream:
    config.write(stream, space_around_delimiters=False)
os.chmod(temporary, 0o640)
os.chown(temporary, 1000, 1000)
temporary.replace(path)
for directory in [config_dir.parent, config_dir,
                  root / 'media/torrents-m920/complete',
                  root / 'media/torrents-m920/incomplete']:
    directory.mkdir(parents=True, exist_ok=True)
    os.chown(directory, 1000, 1000)
    os.chmod(directory, 0o750)
print('M920 qBittorrent configuration reconciled.')
