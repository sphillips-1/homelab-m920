# ShelfGoblin Android

Custom Audiobookshelf Android client with Author → Series → Book and Series →
Author → Book trees. The grouping toggle sits beside All books, Downloaded,
and In progress. Search includes titles, authors and series; each book opens
the inherited detail/playback/download screen. Book rows are text-only, without
cover thumbnails or row icons; expandable author/series nodes retain disclosure
indicators. Podcasts retain the official UI.
Named series are alphabetical, with the Standalone books bucket last in both
Series grouping and each author's branches. The latest played book's author and
series are pinned above that order and marked Recent; book sequence is preserved.
Single-author series open directly to books in Series view and omit repeated
author lines on book rows in both views. Mixed-author series retain author
branches and labels; this is determined before search/download filters.
Recency uses the newest local/server progress timestamp with listening progress
or finished status. ABS progress edits can also update that timestamp. Filtering
never substitutes an older book as recent.
The tree supports ABS 2.36's compact `authorName`/`seriesName` list fields as
well as expanded relationships. The existing library filter catalog supplies
canonical names and IDs, preserving multi-series membership, sequence numbers
and names containing commas without fetching every book individually.

**Settings → List font size** adjusts tree text from 14 to 24 px (default 16),
with a live preview and reset button. Author/series headings, book titles and
details scale together. The choice is stored on the device and restored when
the library opens; the rest of the app keeps its normal text sizes.

## Architecture

ShelfGoblin's default theme matches the Authentik login branding: parchment,
walnut, brass and forest green, with serif library headings. Login uses the
same repository-owned bookshelf background and logo; the app bar uses the
goblin mark. Android launcher icons use the same SVG artwork, converted to
native vectors with adaptive and monochrome variants. The preparer copies these SVG assets into the app for offline use.
Choose **Settings → Theme → ShelfGoblin** after upgrading if a previous theme
was saved. Dark, Black and Light remain available. Theme changes are local
to the app and do not change Authentik or the M920 server.

This is a reproducible overlay on the official GPL-3.0
[Audiobookshelf app](https://github.com/advplyr/audiobookshelf-app), pinned to
`609f9d644c8390fc662869e08ace18ce4a519b00` (0.14.2-beta).
`prepare.cjs` obtains that source, applies branding/authentication edits and
copies `overlay/` into the build checkout. Run it repeatedly without stacking
patches. Keep customization in the overlay/preparer; running preparation replaces
edits to the managed upstream files. The ignored checkout, dependencies, APKs,
and device data do not belong in the homelab source tree.

Native playback, notification controls, Android Auto, bookmarks, chapters, sleep
timer, ebooks, offline downloads and progress sync are inherited. They still
require device acceptance testing; inheritance is not proof of full parity.
The initial tree loads metadata in pages of 200; this is a client operation and
introduces no new M920 service. Downloaded filters use this app's native database
and current server/user connection. If library loading fails, use the inherited
Downloads screen for offline listening. Tree browsing is not yet offline cached.

The application ID is `dev.shelfgoblin.abs` (`.debug` for debug builds).
The inherited Java namespace is intentionally retained. The app installs beside
the official client; existing downloads and saved connections are not shared.

## M920 and SSO

Default server: `https://audiobooks.shelfgoblin.dev/audiobookshelf`.
Keep the `/audiobookshelf` base path. Native Authentik OIDC uses the external
browser, PKCE S256, state validation and ABS's existing token exchange/refresh
flow. The app receives `shelfgoblin://oauth`. No Authentik client secret goes
into the app. ABS continues using its confidential provider and existing HTTPS
callbacks. Group authorization (`audiobooks-users`) and deliberately provisioned
ABS users remain enforced by the server. Cloudflare Tunnel routing stays as-is;
do not add Cloudflare Access or proxy authentication to this hostname.

The homelab reconciler adds the exact mobile URI alongside existing client
callbacks. Deploy through the normal homelab process, or run from the canonical
M920 checkout after the updated script is present:

```bash
sudo docker exec -i authentik-invitation-provisioner python - \
  < /opt/homelab/scripts/reconcile-audiobookshelf-clients.py
```

This changes only ABS's allowed mobile callbacks. It does not enable passwords,
change Authentik provider redirects, or grant groups. Server state stays under
`/srv/homelab/appdata/audiobookshelf`; infrastructure stays under `/opt/homelab`.
To revoke this client, remove its URI from the reconciler and ABS Authentication
settings. Reverting source alone does not remove a persisted allowlist entry.

The callback was added and verified on the live M920 on 2026-10-12 using this
reconciler. A public PKCE sign-in kickoff accepted it and returned an HTTPS
Authentik redirect with state. Completing Google login and returning to the app
still requires the phone acceptance check below.

## Build

Requires Git, Node 22, Java 21, Android SDK platform 36 and build-tools 35.0.0.
Java 21 runs the Capacitor 7 build; inherited Kotlin uses its Java 17 toolchain.
The GitHub Actions workflow builds a debug APK and publishes a GitHub prerelease
on `main` and the initial `codex/shelfgoblin-android` delivery branch. PRs only
build/test and upload Actions artifacts; they cannot publish releases or access
the signing key. Open the repository's **Releases** page on your phone and tap
**ShelfGoblin.apk** under the newest ShelfGoblin build. Assets also include
SHA256SUMS and matching upstream/customization source archives.

After successful publication, a separate Actions job posts the APK download,
release notes/source and build links to Discord **#releases-mobile**. Create an
incoming webhook in that channel and store its URL as the repository Actions
secret `DISCORD_RELEASES_MOBILE_WEBHOOK`. Keep the URL out of Git and chat.
PR builds, failed builds and failed publications do not send announcements.
Discord must confirm delivery; missing configuration or delivery errors fail
the notification job while leaving the published APK available. Rerun only the
failed notification job to retry delivery; rerunning a successful notification
can send a duplicate message. Notifications do not ping everyone or roles.

Publishing requires the encrypted Actions secret
`SHELFGOBLIN_DEBUG_KEYSTORE_BASE64`, containing the existing debug keystore.
That stable key lets CI builds update the local APK without removing the app
and its downloads. Never commit the keystore. The pipeline increments Android
version codes using the workflow run number, starting above the local builds.
These are personal test builds, not Google Play releases. No M920 or Authentik
credentials are used by the build.
Local Windows commands from this directory:

```powershell
node prepare.cjs
npm.cmd ci
npm.cmd test
Push-Location upstream
npm.cmd ci --no-audit --no-fund
npm.cmd run generate
npx.cmd cap sync android
Push-Location android
.\gradlew.bat assembleDebug
Pop-Location
Pop-Location
```

Browser tests: after installing both sets of dependencies, run
`npx playwright install chromium` and `node ui.test.cjs` here. They mount the
real Vue library screen with synthetic API data and check expansion, switching,
filters, routes and widths of 320, 390 and 720 pixels. CI runs these checks too.
`PLAYWRIGHT_EXECUTABLE_PATH` can select an existing browser for local testing.

If Gradle reports access-denied errors or rejects OneDrive cloud files as
non-regular inputs, run `node stage-android.cjs <absolute-local-directory>` after
Capacitor sync. This copies native inputs and their Android module sources to
an ordinary local directory, excluding build output. Run Gradle in that staged
`android/` directory using the same SDK and Java environment. Its APK is under
`android/app/build/outputs/apk/debug/`. Choose a staging directory outside
OneDrive; rerun staging after changing or syncing the app.

The initial local web generation, native Kotlin compilation, APK packaging,
tree/authentication tests, server reconciliation tests and browser interaction
checks passed. The workflow repeats these checks before publishing phone downloads.

APK: `upstream/android/app/build/outputs/apk/debug/app-debug.apk`.
SDK location can be supplied through `ANDROID_HOME` or ignored
`upstream/android/local.properties`. Keep signing keys outside Git. Debug builds
are for personal testing; a stable release signing key is needed before distributing
updates. When distributing a GPL-derived APK, provide its matching source,
overlay, revision, build instructions and upstream license notices.

## Phone acceptance checks

1. Install beside the official app and sign in through Authentik/Google using
   an existing authorized ABS account; verify the callback returns to ShelfGoblin.
2. Check book/series ordering, coauthors, standalones, search and both groupings.
3. Stream, seek, pause with the screen locked, switch chapters, change speed,
   add a bookmark, use the sleep timer and check progress from the official app.
4. Download a book, filter to Downloaded, enable airplane mode and play from
   Downloads. Restart the app offline, then reconnect and confirm progress sync.
5. Verify Android Auto, notification/media buttons, podcasts and ebooks.
6. Verify a user without `audiobooks-users` is denied, and expired sessions can
   reauthenticate without losing downloaded books.
