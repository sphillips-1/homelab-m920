# Authentik

Authentik 2026.5.6 provides the identity layer at
`https://auth.shelfgoblin.dev`. PostgreSQL, the server, and the worker use a
private Compose network. Only `authentik-server` also joins the external
`homelab` network, where cloudflared reaches it at
`http://authentik-server:9000`.

Persistent state lives at `/srv/homelab/appdata/authentik`; see
`../../docs/authentik.md` for setup, Google OAuth, recovery, and backup steps.
