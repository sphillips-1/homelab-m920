# Audiobookshelf

Audiobookshelf deployment configuration lives here.

Persistent state:

- `/srv/homelab/appdata/audiobookshelf` → `/config`
- `/srv/homelab/appdata/audiobookshelf/metadata` → `/metadata`

Audiobook media:

- `/srv/homelab/media/audiobooks` → `/audiobooks`

Application data and media are intentionally kept outside the Git repository.

## Access

The web UI is available at `http://<m920q-lan-ip>:13378` on the LAN or
`http://<m920q-tailscale-name-or-ip>:13378` over Tailscale; SSH port forwarding
is not required. Cloudflare Tunnel reaches `audiobookshelf-gateway` over the
Docker `homelab` network when an intentionally protected public route is
enabled. No router port forwarding is required, and the application must not
remain permanently exposed to the Internet without a proven authentication
path. Do not place browser-based Cloudflare Access in front of this hostname
until native-client API and WebSocket compatibility is demonstrated; use
Tailscale for private mobile access meanwhile.

## Mobile app prompt

The nginx gateway owns host port 13378 and injects `mobile-app.js` into HTML.
All three tunnel templates route through it. The backend retains its Docker
name for internal API consumers. Persistent storage is unchanged.

Android browsers offer Audiobookshelf; iPhone/iPad browsers offer AudioBooth.
The user must tap **Open** to launch the installed app. **Get the app** links
to the platform store, and **Continue in browser** dismisses the prompt for
the current tab session. Desktop, installed web apps, embedded Android
WebViews, sign-in/callback paths and public shares skip the prompt.

The launch opens the app, not a specific book or an authenticated connection.
Configure `https://audiobooks.shelfgoblin.dev/audiobookshelf` in the app first.
Browsers cannot reliably detect installation; if opening fails, the store and
browser options remain available. No OAuth tokens are passed to launch URLs.

Schemes were checked against upstream [Audiobookshelf Android manifest](https://github.com/advplyr/audiobookshelf-app/blob/master/android/app/src/main/AndroidManifest.xml)
and [AudioBooth URL registration](https://github.com/AudioBooth/AudioBooth/blob/main/AudioBooth/AudioBooth/Info.plist).

Deploy through the normal container release workflow. It must recreate the
Audiobookshelf service to transfer port 13378 to the gateway and regenerate
the cloudflared configuration using the updated template. Verify on actual
Android Chrome and iOS Safari with and without the apps installed, then check
browser sign-in, native OIDC, streaming/seeking and WebSockets. Run the local
prompt regression checks with `node --test services/audiobookshelf/mobile-app.test.cjs`.
