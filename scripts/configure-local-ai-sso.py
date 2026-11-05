#!/usr/bin/env python3
"""Provision the private OIDC env file without logging credentials."""
import json
import os
from pathlib import Path
import subprocess
import secrets

def preserve_session_key(directory):
    # Preserve the current signing/encryption key before Compose recreates WebUI.
    # The image otherwise generates its default key in the disposable container layer.
    key_file = directory / "open-webui/.webui_secret_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if not key_file.exists():
        probe = subprocess.run([
            "docker", "exec", "local-ai-webui", "python", "-c",
            "from pathlib import Path; "
            "env=dict(item.split(b'=',1) for item in Path('/proc/1/environ').read_bytes().split(b'\\0') if b'=' in item); "
            "key=env.get(b'WEBUI_SECRET_KEY',b'').decode(); "
            "legacy=Path('/app/backend/.webui_secret_key'); "
            "print(key or (legacy.read_text().strip() if legacy.exists() else ''))",
        ], text=True, capture_output=True, timeout=30)
        running = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", "local-ai-webui"],
                                 text=True, capture_output=True, timeout=30)
        previous_key = probe.stdout.strip() if probe.returncode == 0 else ""
        if running.returncode == 0 and running.stdout.strip() == "true" and not previous_key:
            raise SystemExit("Cannot preserve running WebUI session key; refusing to rotate it implicitly.")
        value = previous_key or secrets.token_urlsafe(48)
        descriptor = os.open(key_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(value + "\n")
    if not key_file.read_text().strip():
        raise SystemExit("Persistent WebUI session key is empty; refusing to start.")
    os.chmod(key_file, 0o600)


def main():
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
    preserve_session_key(directory)
    print("Local AI OIDC configured; credentials remain in private appdata.")


if __name__ == "__main__":
    main()
