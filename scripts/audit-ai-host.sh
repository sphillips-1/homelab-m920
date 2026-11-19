#!/usr/bin/env bash
# Read-only snapshot. Write the report to stdout for local capture.
set -euo pipefail
export LC_ALL=C

section() { printf '\n== %s ==\n' "$1"; }

printf 'Homelab AI resource audit — %s\n' "$(date -u +%FT%TZ)"
section 'CPU and load'
lscpu | awk -F: '$1 == "Model name" || $1 == "CPU(s)"'
uptime
section 'RAM and swap (MiB)'
free -m
section 'Disk capacity'
for path in / /opt/homelab /srv/homelab/appdata; do
    if [[ -d "$path" ]]; then
        printf '\n%s\n' "$path"
        df -h --output=size,used,avail,pcent,target "$path"
    else
        printf '%s unavailable\n' "$path"
    fi
done
if [[ -d /srv/homelab/appdata/local-ai/ollama ]]; then
    du -sh /srv/homelab/appdata/local-ai/ollama 2>/dev/null ||
        echo 'Ollama model directory size unavailable.'
fi

section 'AI and monitoring processes (names only)'
pattern='ollama|open.?webui|aider|opencode|prometheus|grafana|node.exporter|alertmanager|cadvisor|loki|alloy|ntfy|beszel'
ps -eo pid,comm,%cpu,rss | awk -v pattern="$pattern" 'NR == 1 || tolower($2) ~ pattern'
if command -v systemctl >/dev/null; then
    section 'Running AI and monitoring systemd units'
    if units="$(systemctl list-units --type=service --state=running --no-legend --plain 2>/dev/null)"; then
        awk -v pattern="$pattern" 'tolower($1) ~ pattern {print $1}' <<< "$units"
    else
        echo 'Systemd inventory unavailable.'
    fi
fi

section 'Docker containers (including stopped)'
if command -v docker >/dev/null &&
    docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' 2>/dev/null; then
    section 'Running container resource usage'
    timeout 30 docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.BlockIO}}' 2>/dev/null ||
        echo 'Docker stats unavailable.'
else
    echo 'Docker inventory unavailable.'
fi

section 'Ollama installed and loaded models'
if [[ "$(docker inspect --format '{{.State.Running}}' local-ai-ollama 2>/dev/null || true)" == true ]]; then
    for query in list ps; do
        timeout 15 docker exec local-ai-ollama ollama "$query" 2>/dev/null ||
            printf 'Ollama %s unavailable.\n' "$query"
    done
elif command -v ollama >/dev/null; then
    for query in list ps; do
        OLLAMA_HOST=127.0.0.1:11434 timeout 15 ollama "$query" 2>/dev/null ||
            printf 'Local Ollama %s unavailable.\n' "$query"
    done
else
    echo 'No running repository Ollama container or local Ollama CLI detected.'
fi
