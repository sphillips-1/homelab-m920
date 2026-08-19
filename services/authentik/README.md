# Authentik

Authentik 2026.5.6 provides the identity layer at
`https://auth.shelfgoblin.dev`. PostgreSQL, the server, and the worker use a
private Compose network. Only `authentik-server` also joins the external
`homelab` network, where cloudflared reaches it at
`http://authentik-server:9000`.

Persistent state lives at `/srv/homelab/appdata/authentik`; see
`../../docs/authentik.md` for setup, Google OAuth, recovery, and backup steps.

The Compose project also runs an internal invitation provisioner. It is not
published on a host port. Cloudflare routes only `/invite/*` to its bearer-link
landing endpoint; its account-provisioning endpoint requires an internal shared
secret. Authentik calls that endpoint after verified Google login and before
granting the `audiobooks-users` group. See `../../docs/user-onboarding.md` for
setup and use.

Invitation-only secrets are stored in the ignored, mode-0600
`.env.invitation`, separate from the root-owned primary `.env`. Start from
`.env.invitation.example`.
