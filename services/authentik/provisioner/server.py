#!/usr/bin/env python3
"""Internal, idempotent application-account provisioner."""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ABS_URL = os.environ.get("AUDIOBOOKSHELF_URL", "http://audiobookshelf:80").rstrip("/")
ABS_TOKEN = os.environ["AUDIOBOOKSHELF_API_TOKEN"]
CALIBRE_DB = os.environ.get("CALIBRE_WEB_DB", "/calibre-web/app.db")
PROVISIONER_TOKEN = os.environ["AUTHENTIK_INVITATION_PROVISIONER_TOKEN"]
HANDOFF_TTL_SECONDS = 60 * 60
# Calibre-Web permission bits: download (2) and viewer (256). SSO users need
# both to browse and download books without receiving administrative access.
CALIBRE_READER_ROLE = 258
INVITE_PATH = re.compile(
    r"^/invite/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$"
)
INVITE_CREATOR_PATH = "/invite/new/"

INVITE_CREATOR_HTML = b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Create a media invite</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #151515; color: #f5f5f5; }
    main { width: min(34rem, calc(100% - 2rem)); padding: 2rem; border: 1px solid #444; border-radius: .75rem; background: #202020; box-sizing: border-box; }
    h1 { margin-top: 0; font-size: 1.5rem; }
    p { line-height: 1.5; color: #ccc; }
    button { width: 100%; padding: .8rem 1rem; border: 0; border-radius: .35rem; background: #fd4b2d; color: white; font: inherit; font-weight: 650; cursor: pointer; }
    button:disabled { opacity: .65; cursor: wait; }
    #result { width: 100%; margin-top: 1rem; padding: .65rem; box-sizing: border-box; border: 1px solid #555; border-radius: .35rem; background: #111; color: inherit; }
    #status { min-height: 1.5rem; margin-bottom: 0; }
  </style>
</head>
<body>
  <main>
    <h1>Create a media invite</h1>
    <p>Creates a reusable link that expires in 24 hours and grants access to Audiobookshelf and Books.</p>
    <button id="create" type="button">Create invite and copy link</button>
    <input id="result" type="text" readonly hidden aria-label="Invite link">
    <p id="status" role="status" aria-live="polite"></p>
  </main>
  <script>
    const button = document.querySelector('#create');
    const result = document.querySelector('#result');
    const status = document.querySelector('#status');
    const cookie = name => document.cookie.split('; ').find(row => row.startsWith(name + '='))?.split('=').slice(1).join('=');

    button.addEventListener('click', async () => {
      button.disabled = true;
      status.textContent = 'Creating invite...';
      result.hidden = true;
      try {
        const now = new Date();
        const response = await fetch('/api/v3/stages/invitation/invitations/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-authentik-CSRF': decodeURIComponent(cookie('authentik_csrf') || ''),
          },
          body: JSON.stringify({
            name: 'media-' + now.toISOString().replace(/\\D/g, '').slice(0, 14),
            expires: new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString(),
            flow: '3ed71870-1894-47e9-82c0-4c2c1a0968c2',
            fixed_data: {services: ['audiobookshelf', 'calibre-web'], reusable_link: true},
            single_use: false,
          }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || JSON.stringify(payload));
        const link = location.origin + '/invite/' + payload.pk;
        result.value = link;
        result.hidden = false;
        try {
          await navigator.clipboard.writeText(link);
          status.textContent = 'Invite copied to your clipboard.';
        } catch (_) {
          result.select();
          status.textContent = 'Clipboard access was denied. The link is selected; copy it manually.';
        }
      } catch (error) {
        status.textContent = 'Could not create an invite. Confirm you are signed in as an administrator. ' + error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


def sign_invitation(token, expires):
    payload = f"{token}.{expires}"
    signature = hmac.new(
        PROVISIONER_TOKEN.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def abs_request(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{ABS_URL}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {ABS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def users_matching_email(users, normalized_email):
    return [
        u
        for u in users
        if (u.get("email") or "").strip().lower() == normalized_email
    ]


def provision_audiobookshelf(email, name):
    normalized_email = email.strip().lower()
    users = abs_request("GET", "/api/users").get("users", [])
    matches = users_matching_email(users, normalized_email)
    if len(matches) > 1:
        raise ValueError("multiple Audiobookshelf users have the invited email")
    if matches:
        if not matches[0].get("isActive", True):
            raise ValueError("matching Audiobookshelf user is inactive")
        return {"created": False, "user_id": matches[0]["id"]}

    # OIDC is the login method. A random password preserves a non-empty local
    # credential without creating a password known to either the invitee or admin.
    abs_request(
        "POST",
        "/api/users",
        {
            "username": normalized_email,
            "email": normalized_email,
            "name": name.strip() or normalized_email,
            "password": secrets.token_urlsafe(48),
            "type": "user",
            "isActive": True,
            "permissions": {
                "download": True,
                "update": False,
                "delete": False,
                "upload": False,
                "accessAllLibraries": True,
                "accessAllTags": True,
                "accessExplicitContent": True,
            },
            "librariesAccessible": [],
            "itemTagsAccessible": [],
        },
    )
    # Audiobookshelf versions have returned different create-response shapes.
    # Verify the durable result through the stable user-list endpoint instead.
    users = abs_request("GET", "/api/users").get("users", [])
    matches = users_matching_email(users, normalized_email)
    if len(matches) != 1 or not matches[0].get("isActive", True):
        raise ValueError("Audiobookshelf user creation could not be verified")
    return {"created": True, "user_id": matches[0]["id"]}


def provision_calibre_web(email):
    """Create the native account that Calibre-Web proxy auth requires.

    Calibre-Web 0.6.27 does not auto-create reverse-proxy users.  Its proxy
    login performs a case-insensitive lookup of the configured header in the
    local ``user.name`` column, so verified email is the durable matching key.
    Defaults come from Calibre-Web's own new-user configuration.
    """
    normalized_email = email.strip().lower()
    if not os.path.isfile(CALIBRE_DB):
        raise ValueError("Calibre-Web is not initialized")
    with sqlite3.connect(CALIBRE_DB, timeout=15) as db:
        db.execute("PRAGMA busy_timeout = 15000")
        matches = db.execute(
            'SELECT id, name, email FROM "user" '
            'WHERE lower(name) = ? OR lower(email) = ?',
            (normalized_email, normalized_email),
        ).fetchall()
        unique_ids = {row[0] for row in matches}
        if len(unique_ids) > 1:
            raise ValueError("multiple Calibre-Web users match the invited email")
        if matches:
            user_id, username, existing_email = matches[0]
            if username.lower() != normalized_email:
                raise ValueError(
                    "existing Calibre-Web user must be migrated to use email as username"
                )
            db.execute(
                'UPDATE "user" SET email = ?, '
                "view_settings = COALESCE(view_settings, '{}'), role = role | ? "
                ", locale = COALESCE(locale, 'en') "
                ", default_language = COALESCE(default_language, 'all') "
                ", kobo_only_shelves_sync = COALESCE(kobo_only_shelves_sync, 0) "
                "WHERE id = ?",
                (existing_email or normalized_email, CALIBRE_READER_ROLE, user_id),
            )
            return {"created": False, "user_id": user_id}

        settings = db.execute(
            "SELECT config_default_role, config_default_show, "
            "config_denied_tags, config_allowed_tags, "
            "config_denied_column_value, config_allowed_column_value "
            "FROM settings LIMIT 1"
        ).fetchone()
        if settings is None:
            raise ValueError("Calibre-Web is not initialized")
        cursor = db.execute(
            'INSERT INTO "user" '
            "(name, email, password, role, sidebar_view, denied_tags, allowed_tags, "
            "denied_column_value, allowed_column_value, view_settings, locale, "
            "default_language, kobo_only_shelves_sync) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                normalized_email,
                normalized_email,
                secrets.token_urlsafe(48),
                settings[0] | CALIBRE_READER_ROLE,
                settings[1],
                settings[2] or "",
                settings[3] or "",
                settings[4] or "",
                settings[5] or "",
                "{}",
                "en",
                "all",
                0,
            ),
        )
        return {"created": True, "user_id": cursor.lastrowid}


def provision(email, name, services):
    requested = set(services or [])
    if not requested or requested - {"audiobookshelf", "calibre-web"}:
        raise ValueError("unsupported or empty service list")
    result = {}
    if "audiobookshelf" in requested:
        result["audiobookshelf"] = provision_audiobookshelf(email, name)
    if "calibre-web" in requested:
        result["calibre-web"] = provision_calibre_web(email)
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            return self.respond(200, {"ok": True})
        if self.path == INVITE_CREATOR_PATH:
            return self.respond_html(INVITE_CREATOR_HTML)
        match = INVITE_PATH.fullmatch(self.path)
        if not match:
            return self.respond(404, {"error": "not found"})

        # The cookie is deliberately short-lived. The Authentik policy still
        # verifies the underlying invitation's configured expiry after Google.
        expires = int(time.time()) + HANDOFF_TTL_SECONDS
        cookie = sign_invitation(match.group(1), expires)
        self.send_response(302)
        self.send_header(
            "Set-Cookie",
            "ak_service_invite=" + cookie
            + f"; Max-Age={HANDOFF_TTL_SECONDS}; Path=/; Secure; HttpOnly; SameSite=Lax",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Location", "/source/oauth/login/google/")
        self.end_headers()

    def do_POST(self):
        if self.path != "/provision":
            return self.respond(404, {"error": "not found"})
        supplied_token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if not secrets.compare_digest(supplied_token, PROVISIONER_TOKEN):
            return self.respond(401, {"error": "unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            email = body.get("email", "")
            if not email or "@" not in email:
                return self.respond(400, {"error": "valid email required"})
            self.respond(
                200,
                provision(email, body.get("name", ""), body.get("services", [])),
            )
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.respond(409, {"error": str(error)})
        except (urllib.error.URLError, TimeoutError, sqlite3.Error) as error:
            self.respond(502, {"error": f"application provisioning failed: {error}"})

    def respond(self, status, payload):
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def respond_html(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
