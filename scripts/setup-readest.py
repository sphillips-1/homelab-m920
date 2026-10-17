#!/usr/bin/env python3
"""Create Readest secrets once. Run as root; never prints credentials."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time

root = Path('/srv/homelab/appdata/readest')
for name in ('postgres', 'postgres-config', 'minio'):
    (root / name).mkdir(parents=True, exist_ok=True)
os.chown(root / 'minio', 10001, 10001)
target = Path('/opt/homelab/services/readest/.env')
if not target.exists():
    secret = secrets.token_hex(32)

    def b64(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=')

    def jwt(role):
        head = b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())
        payload = b64(json.dumps({'role': role, 'iss': 'supabase',
                                 'iat': int(time.time()), 'exp': int(time.time()) + 315360000}).encode())
        body = head + b'.' + payload
        return (body + b'.' + b64(hmac.new(secret.encode(), body, hashlib.sha256).digest())).decode()

    example = target.with_name('.env.example').read_text()
    values = dict(line.split('=', 1) for line in example.splitlines()
                  if line and not line.startswith('#') and '=' in line)
    origin = 'https://readest.shelfgoblin.dev'
    values.update(POSTGRES_PASSWORD=secrets.token_hex(32), JWT_SECRET=secret,
                  ANON_KEY=jwt('anon'), SERVICE_ROLE_KEY=jwt('service_role'),
                  MINIO_ROOT_PASSWORD=secrets.token_hex(32), SITE_URL=origin,
                  API_EXTERNAL_URL=origin, SUPABASE_PUBLIC_URL=origin,
                  S3_PUBLIC_ENDPOINT=origin, ADDITIONAL_REDIRECT_URLS=origin + '/auth/callback',
                  DISABLE_SIGNUP='true',
                  READEST_ALLOWED_EMAILS=os.environ.get('READEST_ALLOWED_EMAILS', ''))
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    os.chown(target, 1000, 1000)
print('Readest persistent directories and private environment are ready.')
