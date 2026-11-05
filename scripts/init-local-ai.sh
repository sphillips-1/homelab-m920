#!/usr/bin/env bash
# Invoked by deploy-services.sh through the existing GitHub Actions deployment.
set -euo pipefail

[[ "${EUID}" -eq 0 ]] || { echo "ERROR: Run through the root deployment pipeline." >&2; exit 1; }
REPO_DIR="/opt/homelab"
COMPOSE_FILE="${REPO_DIR}/services/local-ai/compose.yml"
compose() { docker compose -f "${COMPOSE_FILE}" "$@"; }

command -v timeout >/dev/null
docker compose version >/dev/null
install -d -m 0700 /srv/homelab/appdata/local-ai
install -d /srv/homelab/appdata/local-ai/{ollama,open-webui}
python3 "${REPO_DIR}/scripts/configure-local-ai-sso.py"
compose config --quiet
# Official prebuilt images; there is no local Dockerfile to build.
compose up -d --wait --wait-timeout 300 ollama

for model in qwen2.5-coder:3b deepseek-coder:1.3b; do
    if ! compose exec -T ollama ollama show "${model}" >/dev/null 2>&1; then
        echo "==> Downloading ${model}"
        timeout 1200 docker compose -f "${COMPOSE_FILE}" exec -T ollama ollama pull "${model}"
    fi
    compose exec -T ollama ollama show "${model}" >/dev/null
done

compose up -d --wait --wait-timeout 300 open-webui
echo "Local AI ready: https://ai.shelfgoblin.dev; Ollama remains on localhost:11434."
