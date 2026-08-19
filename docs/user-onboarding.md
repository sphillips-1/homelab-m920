# User onboarding and offboarding

This runbook covers public Audiobookshelf and Books access through Authentik.
Google authentication creates an identity; it does not grant application
access unless it follows an active reusable service-invitation link.

## Access model

- `audiobooks-users` grants access to the Audiobookshelf OIDC application.
- `books-users` grants access to the Authentik-protected Books application.
- Audiobookshelf auto-registration is disabled. Every authorized identity must
  match an active Audiobookshelf user by email.
- Calibre-Web retains its own users and permissions behind the Authentik proxy.
- Tailscale is not required for public access.

Ordinary Google enrollment never adds an application group automatically. The
Audiobookshelf invitation path is the narrow exception: it requires a valid
signed link handoff and a verified Google email, provisions the local account
first, and only then adds `audiobooks-users`.

## Invite a new Audiobookshelf user

1. In Audiobookshelf Admin, copy the root/admin API token from the root user's
   settings into `AUDIOBOOKSHELF_API_TOKEN` in the protected
   `services/authentik/.env`. Generate and add the internal
   `AUTHENTIK_INVITATION_PROVISIONER_TOKEN` as shown in `.env.example`. This is
   a one-time setup. Redeploy the Authentik Compose project and rerender the
   tunnel's SSO configuration so `/invite/*` reaches the landing endpoint:

   ```bash
   sudo bash /opt/homelab/scripts/configure-cloudflared.sh --mode sso
   ```
2. On the server, create a reusable invitation (24 hours by default). The first
   argument is an administrative label, not an email address:

   ```bash
   sudo bash /opt/homelab/scripts/create-service-invitation.sh friends-and-family
   ```

   To choose another lifetime, pass hours as the second argument.
3. Send the printed URL to the people being invited. Each recipient opens it
   and signs in with Google. Anyone possessing the link can enroll while it is
   valid, so treat it as a temporary credential and do not post it publicly.
4. Confirm that Authentik added the user to `audiobooks-users`, Audiobookshelf
   created an active non-admin user with the same email, and the user can log in.

The local Audiobookshelf password is random and is not shown to the invitee or
administrator; OIDC is the credential they use. New invited accounts can play
and download, cannot modify/upload/delete library content, and initially have
access to all libraries and tags. Adjust those defaults in
`services/authentik/provisioner/server.py` before deploying if needed.

Provisioning is idempotent. If an active Audiobookshelf account already has the
email, it is reused. Duplicate or inactive matches fail closed, and Authentik
does not grant the group. The invitation remains reusable until its configured
expiry. Opening it creates a signed, HttpOnly handoff cookie valid for 15
minutes, allowing Authentik to prove that Google login began from the link
despite the external redirect. Each Google identity receives a separate
Audiobookshelf account.

## Manual Audiobookshelf approval

1. Ask the user to open
   `https://audiobooks.shelfgoblin.dev/audiobookshelf/` and choose the
   Authentik/Google login once.
2. Authentik creates the identity through `google-source-enrollment`. The user
   may see access denied after enrollment; this is expected until approval.
3. In Authentik Admin, open **Directory -> Users**, locate the new identity,
   and copy its verified Google email exactly.
4. In Audiobookshelf Admin, open **Settings -> Users** and create an active
   user with that exact email. Choose the intended library and download,
   playback, and administrative permissions. Do not grant root/admin access
   unless it is genuinely required.
5. Return to Authentik, edit the identity, and add `audiobooks-users`.
6. Ask the user to start a fresh login. Confirm that they see only the intended
   libraries and permissions.

Create the Audiobookshelf user before granting the Authentik group. Otherwise
Authentik will issue a valid token that Audiobookshelf rejects because no
matching local account exists.

## Existing Audiobookshelf user

Use this procedure to preserve the user's ID, progress, bookmarks, history,
permissions, and stored password hash. Password authentication is currently
disabled globally, but preserving the record keeps rollback possible.

1. In Audiobookshelf Admin, edit the existing user; do not delete or recreate
   it.
2. Set its email to the user's exact Google email and confirm it is active.
3. Have the user attempt Google login once so Authentik creates the identity.
4. In Authentik Admin, confirm the identity has the same email, then add it to
   `audiobooks-users`.
5. Have the user retry in a fresh browser or mobile login session and verify
   their existing progress and history.

The Authentik username and Audiobookshelf username may differ. Email is the
matching key and must be identical.

## Books access

1. Have the user authenticate with Google once to create their Authentik
   identity.
2. Add the identity to `books-users`.
3. Create or map the corresponding native Calibre-Web user and permissions
   after Calibre-Web's initial library setup is complete.
4. Test `https://books.shelfgoblin.dev/` in a fresh session.

Authentik protects the browser route, but Calibre-Web still enforces its own
account permissions. Ordinary OPDS clients cannot complete interactive
Authentik login; do not expose an unauthenticated OPDS bypass.

## Browser and mobile setup

Browser users open:

```text
https://audiobooks.shelfgoblin.dev/audiobookshelf/
```

In the official Audiobookshelf Android/iOS app, use this server URL and choose
the Authentik/OpenID login:

```text
https://audiobooks.shelfgoblin.dev/audiobookshelf
```

After a failed or interrupted mobile login, completely close the authentication
window and begin a new login. Reusing an old callback can produce a state
parameter mismatch.

## Troubleshooting

### Enrollment is denied for this account

Confirm the Google source uses `google-source-enrollment`. The dedicated flow
creates the identity but assigns no application groups. Do not switch it back
to `default-source-enrollment`.

For an invitation, confirm that the link has not expired, the user opened it no
more than 15 minutes before completing Google login, and
`authentik-invitation-provisioner` is healthy.

### Access denied

The identity exists but lacks the required group. Add `audiobooks-users` or
`books-users` as appropriate. Group assignment is intentionally manual.

### SSO token unavailable or Unauthorized

Check Audiobookshelf logs:

```bash
docker logs --since 15m audiobookshelf
```

If the log says `User not found and auto-register is disabled`, create or edit
the Audiobookshelf user so its email exactly matches Authentik and ensure the
user is active. Then start a fresh login.

If the log says `State parameter mismatch`, discard the old mobile/browser
authentication window and restart login from the app.

### User reaches Audiobookshelf but has wrong access

Correct the local Audiobookshelf user's library and feature permissions.
Authentik groups grant entry to the application; they do not define
Audiobookshelf's internal permissions.

## Offboarding and access changes

1. Remove `audiobooks-users` to revoke public Audiobookshelf SSO.
2. Remove `books-users` to revoke public Books access.
3. For full revocation, remove both groups and deactivate the Authentik user.
4. Disable the corresponding Audiobookshelf and Calibre-Web users. Preserve
   them rather than deleting them when progress or history may be needed.
5. Test in a private browser session and record the administrative change.

Removing one application group does not revoke the other application.
Audiobookshelf uses OpenID exclusively on public, LAN, and Tailscale paths, so
removing `audiobooks-users` revokes its interactive login everywhere. Disable
the application user too when tokens or existing sessions must be invalidated.
