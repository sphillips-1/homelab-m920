"""Private Authentik-to-GoTrue session adapter; reachable only via the gateway.

Only Authentik's proxy supplies the identity. The gateway has no host port.
Accounts must already exist and be explicitly allowlisted; signup stays off.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def api(path, data):
    request = Request('http://auth:9999/' + path,
                      data=json.dumps(data).encode(),
                      headers={'Authorization': 'Bearer ' + os.environ['SERVICE_ROLE_KEY'],
                               'Content-Type': 'application/json'})
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def session(email):
    allowed = {x.strip().lower() for x in os.environ['READEST_ALLOWED_EMAILS'].split(',')}
    if not email or email.lower() not in allowed:
        raise PermissionError('Identity is not approved')
    link = api('admin/generate_link', {'type': 'magiclink', 'email': email})
    # Consume the single-use token server-side. Never send the admin key or
    # magic-link token to the browser; only its own normal user session.
    return api('verify', {'type': 'magiclink', 'token_hash': link['hashed_token']})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path != '/sso':
            self.send_error(404)
            return
        try:
            result = session(self.headers.get('X-authentik-email', '').strip())
            fragment = urlencode({key: result[key] for key in
                                  ('access_token', 'refresh_token', 'expires_in', 'token_type')})
            self.send_response(302)
            self.send_header('Location', '/auth/callback#' + fragment + '&next=/library')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Length', '0')
            self.end_headers()
        except PermissionError:
            self.send_error(403, 'Readest access is not approved')
        except Exception:
            self.send_error(502, 'Readest sign-in temporarily unavailable')


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8081), Handler).serve_forever()
