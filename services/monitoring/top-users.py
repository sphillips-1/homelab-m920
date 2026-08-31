#!/usr/bin/env python3
"""Render a small, read-only leaderboard from homelab application activity."""

from __future__ import annotations

import html
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


WINDOW_DAYS = max(1, int(os.getenv("TOP_USERS_WINDOW_DAYS", "7")))
CACHE_SECONDS = max(30, int(os.getenv("TOP_USERS_CACHE_SECONDS", "300")))
ALIASES = {str(k).casefold(): str(v) for k, v in json.loads(os.getenv("TOP_USERS_ALIASES", "{}")).items()}
cache = {"at": 0.0, "value": None}
cache_lock = threading.Lock()


def canonical(name: str) -> str:
    value = name.strip()
    return ALIASES.get(value.casefold(), value)


def api_json(base: str, path: str, token: str, header: str) -> object:
    request = urllib.request.Request(
        urllib.parse.urljoin(base.rstrip("/") + "/", path.lstrip("/")),
        headers={header: token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def audiobookshelf_activity() -> dict[str, float]:
    token = os.getenv("AUDIOBOOKSHELF_API_TOKEN", "")
    if not token:
        raise RuntimeError("AUDIOBOOKSHELF_API_TOKEN is not configured")
    base = os.getenv("AUDIOBOOKSHELF_URL", "http://audiobookshelf:80")
    users_payload = api_json(base, "/api/users", token, "Authorization")
    users = users_payload.get("users", users_payload) if isinstance(users_payload, dict) else users_payload
    totals: dict[str, float] = {}
    for user in users:
        user_id = str(user["id"])
        stats = api_json(base, f"/api/users/{urllib.parse.quote(user_id)}/listening-stats", token, "Authorization")
        days = stats.get("days", {}) if isinstance(stats, dict) else {}
        cutoff = time.time() - WINDOW_DAYS * 86400
        seconds = 0.0
        if isinstance(days, dict):
            for day, value in days.items():
                try:
                    if time.mktime(time.strptime(day[:10], "%Y-%m-%d")) >= cutoff:
                        seconds += float(value)
                except (TypeError, ValueError):
                    continue
        if seconds:
            totals[canonical(str(user.get("username") or user.get("email") or user_id))] = seconds
    return totals


def build_report() -> dict[str, object]:
    try:
        seconds = audiobookshelf_activity()
        rows = [{"name": name, "hours": value / 3600} for name, value in seconds.items()]
        rows.sort(key=lambda row: (-row["hours"], str(row["name"]).casefold()))
        return {"rows": rows, "error": "", "generated": time.time()}
    except Exception as exc:
        return {"rows": [], "error": str(exc), "generated": time.time()}


def report() -> dict[str, object]:
    with cache_lock:
        if cache["value"] is None or time.time() - cache["at"] >= CACHE_SECONDS:
            cache["value"] = build_report()
            cache["at"] = time.time()
        return cache["value"]


def render_page(data: dict[str, object]) -> bytes:
    rows = []
    for rank, row in enumerate(data["rows"], 1):
        rows.append(f"<tr><td>{rank}</td><td>{html.escape(str(row['name']))}</td><td>{row['hours']:,.1f}</td></tr>")
    error = html.escape(str(data["error"]))
    body = f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Top listeners</title><style>
:root{{color-scheme:dark;font-family:system-ui,sans-serif;background:#111827;color:#e5e7eb}}body{{max-width:72rem;margin:auto;padding:2rem}}a{{color:#93c5fd}}table{{width:100%;border-collapse:collapse;background:#1f2937;border-radius:.75rem;overflow:hidden}}th,td{{padding:.8rem;text-align:right;border-bottom:1px solid #374151}}th:nth-child(2),td:nth-child(2){{text-align:left}}th{{color:#9ca3af}}.note{{color:#9ca3af}}.errors{{color:#fca5a5}}</style>
<p><a href='/'>← System status</a></p><h1>Top listeners</h1><p class=note>Audiobookshelf listening time during the last {WINDOW_DAYS} days.</p>
<table><thead><tr><th>#</th><th>User</th><th>Hours listened</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan=3>No listening activity is available yet.</td></tr>'}</tbody></table>
<p class=note>Refreshed every {CACHE_SECONDS // 60 or 1} minutes.</p>{f'<p class=errors>{error}</p>' if error else ''}</html>"""
    return body.encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            payload, content_type, status = b"ok\n", "text/plain", 200
        elif self.path in ("/", ""):
            payload, content_type, status = render_page(report()), "text/html; charset=utf-8", 200
        else:
            payload, content_type, status = b"not found\n", "text/plain", 404
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "private, no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.address_string()} - {message % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
