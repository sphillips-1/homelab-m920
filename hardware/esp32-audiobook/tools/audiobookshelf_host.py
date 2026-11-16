"""Serve Audiobookshelf books in the CYD's offline PCM format on a trusted LAN."""
import argparse
from base64 import b64encode
import getpass
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

ID = re.compile(r"[a-zA-Z0-9_-]{1,64}")
PAGE_SIZE = 4
SAMPLE_RATE = 22050


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Library:
    def __init__(self, url, key, cache, ffmpeg):
        self.url = url.rstrip("/")
        self.key = key
        self.cache = cache
        self.ffmpeg = ffmpeg
        self.opener = build_opener(NoRedirect())
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.lock = Lock()
        self.jobs = {}

    def request(self, path):
        # Keep the Audiobookshelf key on the host and restrict it to the configured origin.
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Invalid Audiobookshelf path")
        return self.opener.open(Request(self.url + path, headers={
            "Authorization": "Bearer " + self.key,
        }), timeout=30)

    def json(self, path):
        with self.request(path) as response:
            return json.load(response)

    def libraries(self, page):
        entries = [item for item in self.json("/api/libraries")["libraries"] if item["mediaType"] == "book"]
        return entries[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], len(entries) > (page + 1) * PAGE_SIZE

    def books(self, library, page, series=None):
        query = {"limit": PAGE_SIZE, "page": page, "minified": 1}
        if series:
            query["filter"] = "series." + b64encode(series.encode("ascii")).decode("ascii")
        else:
            query["sort"] = "media.metadata.title"
        result = self.json(f"/api/libraries/{library}/items?" + urlencode(query))
        entries = [{"id": item["id"], "name": item["media"]["metadata"].get("title") or "Untitled"}
                   for item in result["results"]]
        return entries, result["total"] > (page + 1) * PAGE_SIZE

    def recent(self):
        seen = set()
        page = 0
        while True:
            sessions = self.json(f"/api/me/listening-sessions?itemsPerPage=20&page={page}")
            for session in sessions["sessions"]:
                book = session.get("libraryItemId") or ""
                if session.get("mediaType") != "book" or not ID.fullmatch(book) or book in seen:
                    continue
                seen.add(book)
                try:
                    item = self.json(f"/api/items/{book}?minified=1")
                except HTTPError as error:
                    if error.code in (403, 404):
                        continue
                    raise
                meta = item["media"]["metadata"]
                library = item.get("libraryId") or ""
                series = (next((series for series in meta.get("series") or []
                                if ID.fullmatch(series.get("id") or "")), {})
                          if ID.fullmatch(library) else {})
                return (book, meta.get("title") or session.get("displayTitle") or "Untitled",
                        library if series else "", series.get("id", ""), series.get("name") or "")
            page += 1
            if not sessions["sessions"] or page >= sessions.get("numPages", 1):
                return None

    def prepare(self, book):
        target = self.cache / book
        if (target / "manifest.json").is_file():
            return
        item = self.json(f"/api/items/{book}?expanded=1")
        media = item["media"]
        tracks = sorted(media.get("tracks", []), key=lambda track: track["index"])
        if not tracks:
            raise ValueError("Book has no audio tracks")
        with tempfile.TemporaryDirectory(prefix="prepare-", dir=self.cache) as temporary:
            temp = Path(temporary)
            output = temp / "book"
            output.mkdir()
            parts = []
            for number, track in enumerate(tracks, 1):
                content = track["contentUrl"]
                prefixes = (f"/api/items/{book}/file/", f"/s/item/{book}/")
                if not content.startswith(prefixes):
                    raise ValueError("Unexpected audio URL")
                source = temp / "source.audio"
                path = quote(content, safe="/%")
                with self.request(path) as response, source.open("wb") as file:
                    shutil.copyfileobj(response, file, 128 * 1024)
                subprocess.run([
                    self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-i", str(source), "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE),
                    "-c:a", "pcm_s16le", "-f", "segment", "-segment_format", "s16le",
                    "-segment_time", "900", str(temp / "segment-%05d.pcm"),
                ], check=True, capture_output=True, timeout=1800)
                source.unlink()
                for segment in sorted(temp.glob("segment-*.pcm")):
                    size = segment.stat().st_size
                    if size < 2 or size % 2:
                        raise ValueError("Invalid converted audio")
                    name = f"{len(parts) + 1:05d}.pcm"
                    segment.rename(output / name)
                    parts.append({"name": name, "bytes": size})
            if not parts:
                raise ValueError("Conversion produced no audio")
            title = media["metadata"].get("title", "Untitled")
            (output / "manifest.json").write_text(json.dumps({"title": title, "parts": parts}),
                                                   encoding="utf-8")
            output.rename(target)

    def start(self, book):
        with self.lock:
            job = self.jobs.get(book)
            if job is None or job.done():
                self.jobs[book] = self.executor.submit(self.prepare, book)

    def status(self, book):
        manifest = self.cache / book / "manifest.json"
        if manifest.is_file():
            return json.loads(manifest.read_text(encoding="utf-8"))
        with self.lock:
            job = self.jobs.get(book)
            if job is not None and job.done() and job.exception() is not None:
                print(f"Preparation failed for {book}: {type(job.exception()).__name__}", flush=True)
                raise ValueError("Book preparation failed on host")
        return None


def label(text):
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(text)).encode("ascii", "replace").decode()[:90]


def handler(library, key):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, text):
            body = text.encode("ascii")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), key):
                self.reply(401, "Unauthorized")
                return False
            return True

        def do_POST(self):
            if not self.authorized():
                return
            match = re.fullmatch(r"/book/([A-Za-z0-9_-]{1,64})", self.path)
            if not match:
                self.reply(404, "Not found")
                return
            library.start(match[1])
            self.reply(202, "Preparing")

        def do_GET(self):
            if not self.authorized():
                return
            try:
                self.get()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (ValueError, KeyError, OSError, URLError) as error:
                print(f"Request failed: {type(error).__name__}", flush=True)
                self.reply(502, "Audiobook host or server error")

        def get(self):
            path = self.path.strip("/").split("/")
            if path == ["recent"]:
                recent = library.recent()
                if recent:
                    book, title, collection, series, name = recent
                    self.reply(200, "\t".join((book, label(title), collection, series, label(name))))
                else:
                    self.reply(200, "")
                return
            if path[0] in ("libraries", "books", "series"):
                page = int(path[-1])
                if not 0 <= page <= 10000:
                    raise ValueError("Invalid page")
                if path[0] == "libraries" and len(path) == 2:
                    entries, more = library.libraries(page)
                elif path[0] == "books" and len(path) == 3 and ID.fullmatch(path[1]):
                    entries, more = library.books(path[1], page)
                elif (path[0] == "series" and len(path) == 4 and
                      ID.fullmatch(path[1]) and ID.fullmatch(path[2])):
                    entries, more = library.books(path[1], page, series=path[2])
                else:
                    raise ValueError("Invalid catalog request")
                rows = [f"{item['id']}\t{label(item['name'])}" for item in entries if ID.fullmatch(item["id"])]
                self.reply(200, str(int(more)) + "\n" + "\n".join(rows))
                return
            if len(path) >= 2 and path[0] == "book" and ID.fullmatch(path[1]):
                book = path[1]
                status = library.status(book)
                if status is None:
                    self.reply(202, "Preparing")
                elif len(path) == 2:
                    sizes = ",".join(str(part["bytes"]) for part in status["parts"])
                    self.reply(200, label(status["title"]) + "\n" + sizes)
                elif len(path) == 3 and re.fullmatch(r"\d{5}\.pcm", path[2]):
                    file = library.cache / book / path[2]
                    if not file.is_file():
                        self.reply(404, "Audio part not found")
                        return
                    with file.open("rb") as audio:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(file.stat().st_size))
                        self.end_headers()
                        shutil.copyfileobj(audio, self.wfile, 64 * 1024)
                else:
                    self.reply(404, "Not found")
                return
            self.reply(404, "Not found")
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="https://audiobooks.shelfgoblin.dev")
    parser.add_argument("--bind", required=True, help="host's private LAN IPv4 address")
    parser.add_argument("--port", type=int, default=8784)
    parser.add_argument("--container", action="store_true", help="bind behind the Docker LAN port")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    import ipaddress
    bind = ipaddress.IPv4Address(args.bind)
    if not (bind.is_private and not bind.is_unspecified or args.container and bind.is_unspecified):
        parser.error("--bind must be a private LAN IPv4 address")
    url = urlsplit(args.server)
    internal = args.container and args.server == "http://audiobookshelf"
    if not internal and (url.scheme != "https" or not url.hostname or url.username or url.query or url.fragment):
        parser.error("--server must be an HTTPS URL")
    ffmpeg = shutil.which(args.ffmpeg)
    if not ffmpeg:
        parser.error("FFmpeg is required")
    args.cache.mkdir(parents=True, exist_ok=True)
    token_file = args.cache / "cyd-token.txt"
    if not token_file.exists():
        with os.fdopen(os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as file:
            file.write(secrets.token_urlsafe(32))
    token = token_file.read_text().strip()
    abs_key = os.environ.get("CYD_ABS_API_KEY")
    if not abs_key:
        if args.container:
            parser.error("CYD_ABS_API_KEY is required")
        abs_key = getpass.getpass("Audiobookshelf API key: ")
    library = Library(args.server, abs_key, args.cache, ffmpeg)
    with ThreadingHTTPServer((args.bind, args.port), handler(library, ("Bearer " + token).encode())) as server:
        print(f"CYD audiobook host at http://{args.bind}:{args.port}", flush=True)
        print("Use the contents of cyd-token.txt in the CYD's network configuration.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
