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
INVITE_PATH = re.compile(
    r"^/invite/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$"
)


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
            if not existing_email:
                db.execute(
                    'UPDATE "user" SET email = ? WHERE id = ?',
                    (normalized_email, user_id),
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
            "denied_column_value, allowed_column_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                normalized_email,
                normalized_email,
                secrets.token_urlsafe(48),
                settings[0],
                settings[1],
                settings[2] or "",
                settings[3] or "",
                settings[4] or "",
                settings[5] or "",
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

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
