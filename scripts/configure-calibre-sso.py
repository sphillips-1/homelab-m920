#!/usr/bin/env python3
"""Enable Calibre-Web proxy login and optionally map a legacy user to SSO."""

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def normalized_email(value):
    value = value.strip().lower()
    if not value or "@" not in value:
        raise argparse.ArgumentTypeError("a valid email address is required")
    return value


parser = argparse.ArgumentParser()
parser.add_argument("--database", default="/srv/homelab/appdata/calibre-web/app.db", type=Path)
parser.add_argument("--map-user", help="existing Calibre-Web username to preserve")
parser.add_argument("--email", type=normalized_email, help="verified Authentik email")
args = parser.parse_args()
if bool(args.map_user) != bool(args.email):
    parser.error("--map-user and --email must be supplied together")
if not args.database.is_file():
    parser.error(f"Calibre-Web database not found: {args.database}")

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = args.database.with_name(f"{args.database.name}.pre-sso-{stamp}")
shutil.copy2(args.database, backup)

try:
    with sqlite3.connect(args.database, timeout=15) as db:
        db.execute("PRAGMA busy_timeout = 15000")
        columns = {row[1] for row in db.execute("PRAGMA table_info(settings)")}
        required = {"config_allow_reverse_proxy_header_login", "config_reverse_proxy_login_header_name"}
        if not required <= columns:
            raise RuntimeError("this Calibre-Web database lacks proxy-login settings")
        db.execute(
            "UPDATE settings SET config_allow_reverse_proxy_header_login = 1, "
            "config_reverse_proxy_login_header_name = 'X-authentik-email'"
        )
        if args.map_user:
            user = db.execute(
                'SELECT id FROM "user" WHERE lower(name) = ?',
                (args.map_user.strip().lower(),),
            ).fetchone()
            if user is None:
                raise RuntimeError(f"Calibre-Web user not found: {args.map_user}")
            collision = db.execute(
                'SELECT id FROM "user" WHERE id != ? AND (lower(name) = ? OR lower(email) = ?)',
                (user[0], args.email, args.email),
            ).fetchone()
            if collision:
                raise RuntimeError("another Calibre-Web user already uses that email")
            db.execute(
                'UPDATE "user" SET name = ?, email = ? WHERE id = ?',
                (args.email, args.email, user[0]),
            )
except Exception:
    shutil.copy2(backup, args.database)
    raise

print(f"Enabled Calibre-Web SSO header login; backup: {backup}")
if args.map_user:
    print(f"Mapped existing user {args.map_user!r} to {args.email}")
print("Restart calibre-web before testing.")
