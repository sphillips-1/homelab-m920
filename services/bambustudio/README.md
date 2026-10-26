# Bambu Studio browser trial

The normal deployment pipeline manages the Terraform DNS record, deploys the
container, reconciles Authentik, and checks service health and access policies.
It retains the canonical checkout's clean-tree guard.

Shared desktop at https://bambu.shelfgoblin.dev, protected by the Authentik
embedded proxy and explicit `bambu-users` membership. Google login alone and
standard invitations do not grant access. All approved users share projects,
profiles, and any Bambu account signed into Studio. Bambu login remains separate.

Configuration lives here under `/opt/homelab`; persistent files and credentials
stay in `/srv/homelab/appdata/bambustudio` and must never enter Git.
No host ports or Docker socket are mounted. The container joins `homelab` so
Authentik can reach port 3000. HTTPS terminates at Cloudflare; the streaming
WebSocket must pass through Authentik. No GPU is required for the trial.

Deploy: `bash /opt/homelab/scripts/deploy-bambustudio.sh`.
Reconcile the SSO tunnel template with `configure-cloudflared.sh --mode sso`,
validate ingress, and restart cloudflared. Provision the DNS CNAME using the
existing Terraform hostname map. Grant only the intended owner's identity the
`bambu-users` group through Authentik. The image is pinned to the trial digest
(Bambu Studio v02.08.04.57-ls175). Printer login, discovery, and actual slicing require
interactive verification before treating this as production.

Stop with `docker compose -f /opt/homelab/services/bambustudio/compose.yml down`.
Persistent files remain. Remove the hostname route and group access to retire it.

Before updates, stop the container and archive its appdata into a root-only
timestamped directory under `/srv/homelab/backups/bambustudio`, then restart it.
The archive can contain Bambu account credentials; keep off-host copies encrypted.

Verify access using `docker exec -i authentik-worker ak shell <
/opt/homelab/scripts/verify-bambustudio-sso.py` (one shell command). It checks
approved portal visibility, ordinary library user denial, and anonymous redirects
on both the UI and streaming paths without creating login credentials.
