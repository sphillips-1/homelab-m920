"""Install the channel webhook from stdin without logging its value."""

import os
import re
import sys
import tempfile
from pathlib import Path

url = sys.stdin.read(1024).strip()
if not re.fullmatch(r"https://discord\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+", url):
    raise SystemExit("Invalid Discord incoming webhook URL.")

directory = Path("/appdata/ai-investigator")
directory.mkdir(mode=0o700, exist_ok=True)
os.chown(directory, 10001, 10001)
directory.chmod(0o700)
with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as handle:
    temporary = Path(handle.name)
    try:
        os.fchown(handle.fileno(), 10001, 10001)
        handle.write(url + "\n")
        handle.flush()
        temporary.replace(directory / "discord-webhook.url")
    finally:
        temporary.unlink(missing_ok=True)
