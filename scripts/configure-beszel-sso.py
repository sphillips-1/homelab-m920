#!/usr/bin/env python3
"""Reconcile Authentik and Beszel through their supported ORM and REST APIs.

Run as root on the M920. Secrets stay in memory and application databases.
No owner password is read, reset, or stored by this helper.
"""
import copy
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

REPO = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8090"
MARKER = "BESZEL_OIDC_CONFIG="
OPENER = build_opener(ProxyHandler({}))


def request(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    try:
        with OPENER.open(Request(BASE_URL + path, body, headers, method=method), timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        # PocketBase errors may echo submitted credentials. Never print the body.
        raise RuntimeError(f"Beszel {method} {path} failed (HTTP {error.code}).") from None
    except URLError:
        raise RuntimeError(f"Beszel {method} {path} could not connect.") from None


def docker(*args, source=None):
    result = subprocess.run(["docker", *args], input=source, text=True,
                            capture_output=True, timeout=120, check=False)
    if result.returncode:
        # Neither arguments nor captured output are safe to log.
        raise RuntimeError("Beszel SSO Docker operation failed; credentials and output suppressed.")
    return result.stdout


def wait_for_hub():
    for attempt in range(36):
        try:
            request("GET", "/api/health")
            return
        except RuntimeError:
            if attempt == 35:
                raise
            time.sleep(5)


def get_credentials():
    source = (REPO / "scripts/reconcile-beszel-sso.py").read_text()
    output = docker("exec", "-i", "authentik-worker", "ak", "shell", source=source)
    entries = [line[len(MARKER):] for line in output.splitlines() if line.startswith(MARKER)]
    if len(entries) != 1:
        raise RuntimeError("Authentik did not return exactly one Beszel credential marker.")
    try:
        credentials = json.loads(entries[0])
        if set(credentials) != {"clientId", "clientSecret"} or not all(
            isinstance(value, str) and value for value in credentials.values()
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise RuntimeError("Authentik returned invalid Beszel credentials.") from None
    return credentials


def desired_oauth(collection, credentials):
    oauth = copy.deepcopy(collection.get("oauth2", {}))
    oauth["enabled"] = True
    # Only this provider may authenticate dashboard users, including on the LAN.
    oauth["providers"] = [{
        "name": "oidc", "displayName": "Authentik", **credentials,
        "authURL": "https://auth.shelfgoblin.dev/application/o/authorize/",
        "tokenURL": "https://auth.shelfgoblin.dev/application/o/token/",
        "userInfoURL": "https://auth.shelfgoblin.dev/application/o/userinfo/",
        "pkce": True,
    }]
    return oauth


def verify_auth_methods():
    methods = request("GET", "/api/collections/users/auth-methods")
    providers = methods.get("oauth2", {}).get("providers", [])
    if methods.get("password", {}).get("enabled") is not False:
        raise RuntimeError("Beszel dashboard password login is still enabled.")
    if not methods.get("oauth2", {}).get("enabled") or [p.get("name") for p in providers] != ["oidc"]:
        raise RuntimeError("Beszel does not advertise the exclusive Authentik OIDC provider.")


def backup_database():
    # SQLite's online backup API produces a consistent snapshot, including WAL.
    database = Path("/srv/homelab/appdata/monitoring/beszel-data/data.db")
    backup_dir = Path("/srv/homelab/backups/beszel-sso")
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(backup_dir, 0o700)
    target = backup_dir / (time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(4) + ".db")
    try:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(target) as destination:
                source.backup(destination)
    except Exception:
        target.unlink(missing_ok=True)
        raise RuntimeError("Beszel database backup failed; refusing to change authentication.") from None
    print(f"Beszel pre-SSO database backup: {target}")


def configure(credentials):
    email = "sso-deploy-" + secrets.token_hex(12) + "@shelfgoblin.dev"
    password = secrets.token_urlsafe(48)
    # Delete even if creation partially succeeds or a subsequent API request fails.
    try:
        docker("exec", "beszel", "/beszel", "superuser", "create", email, password,
               "--dir", "/beszel_data")
        auth = request("POST", "/api/collections/_superusers/auth-with-password",
                       {"identity": email, "password": password})
        token = auth["token"]
        admins = request("GET", "/api/collections/users/records?perPage=1&filter=role%3D%27admin%27", token=token)
        if not admins.get("totalItems"):
            raise RuntimeError("Create the first Beszel administrator with its Google email, then rerun this helper.")
        collection = request("GET", "/api/collections/users", token=token)
        oauth = desired_oauth(collection, credentials)
        if collection.get("oauth2") != oauth:
            request("PATCH", "/api/collections/users", {"oauth2": oauth}, token=token)
        saved = request("GET", "/api/collections/users", token=token)
        provider = saved.get("oauth2", {}).get("providers", [])
        if len(provider) != 1 or any(provider[0].get(key) != value for key, value in oauth["providers"][0].items()):
            raise RuntimeError("Beszel OAuth settings did not persist as requested.")
        if saved.get("createRule") != "@request.context = 'oauth2'":
            raise RuntimeError("Beszel OAuth-only account creation is not configured.")
        verify_auth_methods()
    finally:
        # Supported CLI cleanup also works if the HTTP API became unavailable.
        docker("exec", "beszel", "/beszel", "superuser", "delete", email,
               "--dir", "/beszel_data")
    print("Beszel native Authentik SSO reconciled and verified; temporary superuser removed.")


def main():
    import fcntl
    if os.geteuid() != 0:
        raise RuntimeError("Run this helper as root on the M920.")
    with open("/run/lock/homelab-beszel-sso.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        wait_for_hub()
        credentials = get_credentials()
        backup_database()
        configure(credentials)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not expose exception arguments, which can include Docker credentials.
        message = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)
