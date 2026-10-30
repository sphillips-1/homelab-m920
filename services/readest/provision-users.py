"""Run in readest-sso with email arguments, before granting Authentik groups."""
import json
import os
import sys
from urllib.request import Request, urlopen
from sso import api

allowed = {item.lower().strip() for item in os.environ['READEST_ALLOWED_EMAILS'].split(',')}
for email in sys.argv[1:]:
    if email.lower() not in allowed:
        raise RuntimeError('Add the email to the private allowlist first')
    matches = []
    for page in range(1, 1000):
        request = Request(f'http://auth:9999/admin/users?page={page}&per_page=100', headers={
            'Authorization': 'Bearer ' + os.environ['SERVICE_ROLE_KEY']})
        with urlopen(request, timeout=15) as response:
            users = json.load(response)['users']
        matches.extend(user for user in users if user.get('email', '').lower() == email.lower())
        if len(users) < 100:
            break
    if len(matches) > 1:
        raise RuntimeError('Duplicate application identities')
    if not matches:
        api('admin/users', {'email': email, 'email_confirm': True})
    print('Readest account ready:', email)
