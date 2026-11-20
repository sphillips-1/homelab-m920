"""Exercise real Alertmanager with a local Discord webhook receiver."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def http(url, payload=None, timeout=2):
    request = Request(url, None if payload is None else json.dumps(payload).encode(),
                      {"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode()


def wait_for(check):
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("Timed out waiting for pilot test result")


class Ollama(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append(data["prompt"])
        if "PilotTimeout" in data["prompt"]:
            time.sleep(13)
            return
        upstream = os.environ.get("PILOT_SMOKE_OLLAMA_URL")
        result = (http(upstream + "/api/generate", data, timeout=11).encode() if upstream
                  else b'{"response":"Synthetic incident summary."}')
        self.send_response(200)
        self.end_headers()
        self.wfile.write(result)

    def log_message(self, *_args):
        pass


class Discord(BaseHTTPRequestHandler):
    messages = []

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.path == "/webhook?wait=true"
        assert payload["allowed_mentions"] == {"parse": []}
        self.messages.append(payload["content"])
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        pass


def main(alertmanager):
    source = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as directory, ExitStack() as resources:
        root = Path(directory)
        am_port, app_port = port(), port()
        am = f"http://127.0.0.1:{am_port}"
        agent = f"http://127.0.0.1:{app_port}/alerts"
        ollama = resources.enter_context(ThreadingHTTPServer(("127.0.0.1", 0), Ollama))
        threading.Thread(target=ollama.serve_forever, daemon=True).start()
        resources.callback(ollama.shutdown)
        discord = resources.enter_context(ThreadingHTTPServer(("127.0.0.1", 0), Discord))
        threading.Thread(target=discord.serve_forever, daemon=True).start()
        resources.callback(discord.shutdown)
        webhook = root / "discord-webhook.url"
        webhook.write_text(f"http://127.0.0.1:{discord.server_port}/webhook")
        config = root / "alertmanager.yml"
        config.write_text((source / config.name).read_text().replace(
            "http://investigator:8080/alerts", agent), encoding="utf-8")
        db = root / "incidents.sqlite3"

        def start(*command, env=None):
            process = subprocess.Popen(command, cwd=source, env=env,
                                       stdout=subprocess.DEVNULL,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            def stop():
                process.terminate()
                process.wait(timeout=5)
            resources.callback(stop)

        start(alertmanager, f"--config.file={config}", f"--storage.path={root / 'am'}",
              f"--web.listen-address=127.0.0.1:{am_port}", "--cluster.listen-address=")
        start(sys.executable, "-m", "uvicorn", "app:app", "--port", str(app_port),
              env=dict(os.environ, INCIDENT_DB=str(db), DISCORD_WEBHOOK_FILE=str(webhook),
                       OLLAMA_URL=f"http://127.0.0.1:{ollama.server_port}",
                       PYTHONDONTWRITEBYTECODE="1"))
        wait_for(lambda: http(am + "/-/ready"))

        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        alert = {"labels": {"alertname": "PilotSynthetic"}, "startsAt": started,
                 "annotations": {"summary": "Synthetic disk alert"}}
        http(am + "/api/v2/alerts", [alert])
        first = wait_for(lambda: Discord.messages)
        assert "\nAI summary: " in first[0], first
        repeated = http(agent, {"alerts": [dict(alert, status="firing")]})
        assert json.loads(repeated) == {"duplicate": True}, repeated
        assert len(Discord.messages) == 1

        http(am + "/api/v2/alerts", [dict(alert, labels={"alertname": "PilotTimeout"})])
        final = wait_for(lambda: Discord.messages if len(Discord.messages) == 2 else None)
        assert any(message == "FIRING PilotTimeout\nSynthetic disk alert" for message in final)
        assert len(Ollama.calls) == 2
        with closing(sqlite3.connect(db)) as connection:
            assert connection.execute("SELECT COUNT(*) FROM incidents WHERE delivered=1").fetchone() == (2,)
        print("Alertmanager delivery, SQLite history, Discord payload, deduplication, and timeout fallback passed.")


if __name__ == "__main__":
    main(*sys.argv[1:])
