"""Run inside readest-sso: native sessions, storage round trip and isolation.

Creates and removes one uniquely named disposable smoke-test object only.
Tokens and presigned URLs are deliberately never printed.
"""
import json
import os
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

sys.path.insert(0, '/app')
from sso import session


def api(path, token, data=None, method=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request('http://gateway:8080/api/storage/' + path, data=body, method=method,
                      headers={'Authorization': 'Bearer ' + token,
                               'Host': 'readest.shelfgoblin.dev', 'Content-Type': 'application/json'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def storage(url, data=None):
    parts = urlsplit(url)
    request = Request('http://gateway:8080' + parts.path + '?' + parts.query, data=data,
                      method='PUT' if data is not None else 'GET', headers={'Host': parts.netloc})
    with urlopen(request, timeout=30) as response:
        return response.read()


emails = [email for email in os.environ['READEST_ALLOWED_EMAILS'].split(',') if email]
assert len(emails) == 2
first, second = [session(email) for email in emails]
assert first['user']['id'] != second['user']['id']
try:
    session('unapproved@example.invalid')
    raise AssertionError('Unapproved session accepted')
except PermissionError:
    pass
name = 'codex-readest-smoke-' + uuid4().hex + '.txt'
body = b'Readest storage verification\n'
uploaded = api('upload', first['access_token'], {'fileName': name, 'fileSize': len(body)})
key = uploaded['fileKey']
try:
    storage(uploaded['uploadUrl'], body)
    download = api('download?' + urlencode({'fileKey': key}), first['access_token'])
    assert storage(download['downloadUrl']) == body
    try:
        api('download?' + urlencode({'fileKey': key}), second['access_token'])
        raise AssertionError('Other user can download private object')
    except HTTPError as error:
        assert error.code == 404
finally:
    api('delete?' + urlencode({'fileKey': key}), first['access_token'], method='DELETE')
print('Separate sessions, unapproved identity denial, signed S3 upload/download, and cross-user isolation passed.')
