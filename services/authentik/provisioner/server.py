#!/usr/bin/env python3
"""Internal, idempotent Audiobookshelf account provisioner."""

import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ABS_URL = os.environ.get("AUDIOBOOKSHELF_URL", "http://audiobookshelf:80").rstrip("/")
ABS_TOKEN = os.environ["AUDIOBOOKSHELF_API_TOKEN"]
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


def provision(email, name):
    normalized_email = email.strip().lower()
    users = abs_request("GET", "/api/users").get("users", [])
    matches = [u for u in users if u.get("email", "").strip().lower() == normalized_email]
    if len(matches) > 1:
        raise ValueError("multiple Audiobookshelf users have the invited email")
    if matches:
        if not matches[0].get("isActive", True):
            raise ValueError("matching Audiobookshelf user is inactive")
        return {"created": False, "user_id": matches[0]["id"]}

    # OIDC is the login method. A random password preserves a non-empty local
    # credential without creating a password known to either the invitee or admin.
    user = abs_request(
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
    return {"created": True, "user_id": user["id"]}


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
            self.respond(200, provision(email, body.get("name", "")))
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.respond(409, {"error": str(error)})
        except (urllib.error.URLError, TimeoutError) as error:
            self.respond(502, {"error": f"Audiobookshelf request failed: {error}"})

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
