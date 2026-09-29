#!/usr/bin/env python3
"""Allow Lissen through the ABS API using the provisioner's existing credentials."""

import json
import os
import time
import urllib.error
import urllib.request


FIELD = "authOpenIDMobileRedirectURIs"
REQUIRED_URIS = ("lissen://oauth",)


def request_settings(method="GET", payload=None):
    token = os.environ.get("AUDIOBOOKSHELF_API_TOKEN")
    if not token:
        raise RuntimeError("AUDIOBOOKSHELF_API_TOKEN is required")
    base = os.environ.get("AUDIOBOOKSHELF_URL", "http://audiobookshelf:80")
    request = urllib.request.Request(
        base.rstrip("/") + "/api/auth-settings",
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def read_settings():
    # Compose starts the service before its API is necessarily ready.
    for attempt in range(30):
        try:
            return request_settings()
        except urllib.error.HTTPError as error:
            if error.code not in (502, 503, 504):
                raise RuntimeError(f"ABS auth-settings request failed (HTTP {error.code})") from None
        except (urllib.error.URLError, TimeoutError):
            pass
        if attempt < 29:
            time.sleep(2)
    raise RuntimeError("ABS auth-settings API did not become ready")


def redirect_uris(settings):
    current = settings.get(FIELD)
    if not isinstance(current, list) or any(not isinstance(uri, str) for uri in current):
        raise RuntimeError("ABS returned an invalid mobile redirect URI list")
    return current


def reconcile():
    current = redirect_uris(read_settings())
    # ABS accepts '*' only as the sole entry. Preserve an existing wildcard.
    if current == ["*"] or all(uri in current for uri in REQUIRED_URIS):
        print("Audiobookshelf already allows Lissen.")
        return
    if "*" in current:
        raise RuntimeError("ABS has a malformed wildcard redirect list")
    desired = current + [uri for uri in REQUIRED_URIS if uri not in current]
    request_settings("PATCH", {FIELD: desired})
    if set(redirect_uris(read_settings())) != set(desired):
        raise RuntimeError("ABS mobile redirect URI verification failed")
    print("Audiobookshelf now allows Lissen; existing mobile callbacks preserved.")


if __name__ == "__main__":
    try:
        reconcile()
    except (RuntimeError, urllib.error.URLError, TimeoutError, ValueError) as error:
        # Do not print API response bodies, settings, or credentials.
        if isinstance(error, RuntimeError):
            raise SystemExit(str(error)) from None
        raise SystemExit("ABS client reconciliation failed; check API availability and credentials.") from None
