#!/usr/bin/env python3
"""Provision the private OIDC env file without logging credentials."""
import json
import os
from pathlib import Path
import subprocess

root = Path("/opt/homelab")
source = (root / "scripts/reconcile-local-ai-sso.py").read_text()
result = subprocess.run(["docker", "exec", "-i", "authentik-worker", "ak", "shell"],
                        input=source, text=True, capture_output=True, timeout=120)
if result.returncode:
    raise SystemExit("Local AI Authentik provisioning failed; private output suppressed.")
entries = [line.removeprefix("LOCAL_AI_OIDC=") for line in result.stdout.splitlines()
           if line.startswith("LOCAL_AI_OIDC=")]
if len(entries) != 1:
    raise SystemExit("Missing unique Local AI credential marker.")
values = json.loads(entries[0])
if set(values) != {"OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET"} or not all(
        isinstance(value, str) and value and "\n" not in value and "\r" not in value
        for value in values.values()):
    raise SystemExit("Invalid Local AI credentials; output suppressed.")
directory = Path("/srv/homelab/appdata/local-ai")
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
temporary = directory / "oidc.env.new"
descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
with os.fdopen(descriptor, "w") as output:
    # JSON double quoting is compatible with Compose env files.
    for key, value in values.items():
        output.write(f"{key}={json.dumps(value)}\n")
os.chmod(temporary, 0o600)
temporary.replace(directory / "oidc.env")
print("Local AI OIDC configured; credentials remain in private appdata.")
