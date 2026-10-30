#!/usr/bin/env bash
set -euo pipefail
cd /opt/homelab
docker run --rm -v /srv/homelab/appdata:/appdata alpine:3.22 \
    sh -c 'mkdir -p /appdata/bambustudio && chown 1000:1000 /appdata/bambustudio'
docker compose -f services/bambustudio/compose.yml config -q
docker compose -f services/bambustudio/compose.yml up -d
docker exec -i authentik-worker ak shell < scripts/reconcile-bambustudio-sso.py
