#!/usr/bin/env python3
"""Run with Python in the M920 qBittorrent network namespace."""
import json
import socket
import urllib.request
import urllib.error

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

opener = urllib.request.build_opener(NoRedirect)
for route in ('/', '/api/v2/app/preferences'):
    try:
        opener.open('http://127.0.0.1:8091' + route, timeout=10)
    except urllib.error.HTTPError as error:
        assert error.code == 302, error.code
        assert '/outpost.goauthentik.io/start' in error.headers['Location']
    else:
        raise AssertionError('Anonymous gateway access was allowed')
request = urllib.request.Request('http://127.0.0.1:8080/api/v2/app/preferences',
                                 headers={'Host': 'torrents.shelfgoblin.dev'})
with urllib.request.urlopen(request, timeout=10) as response:
    preferences = json.load(response)
assert preferences['save_path'].rstrip('/') == '/downloads/complete'
assert preferences['temp_path'].rstrip('/') == '/downloads/incomplete'
assert preferences['web_ui_address'] == '127.0.0.1'
assert preferences['web_ui_csrf_protection_enabled']
assert preferences['web_ui_host_header_validation_enabled']
assert not preferences['bypass_auth_subnet_whitelist_enabled']
assert not preferences['upnp']
address = socket.gethostbyname('m920-qbittorrent')
with socket.socket() as connection:
    connection.settimeout(3)
    assert connection.connect_ex((address, 8080)) != 0, 'Raw Web UI exposed'
print('Anonymous UI/API denied; raw Web UI isolated; paths and security verified.')
