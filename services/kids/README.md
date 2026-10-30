# Curiosity Club

LAN-only, offline activities for children aged 6 and 9 using PCs and keyboards.
The buildless portal has original Snake and Breakout games, a keyboard-accessible
matching puzzle, a mouse drawing pad with PNG export, and an optional EmulatorJS shelf.
No analytics, public chat, remote fonts, CDN scripts, account system, or external
assets are loaded by the portal. Artwork and game progress are not stored on the
server; save drawings before navigating away. Emulator saves remain browser-local.

## Deploy

```bash
cd /opt/homelab
KIDS_LAN_IP=192.168.4.27 bash scripts/deploy-kids.sh
```

The idempotent script copies the selected Jellyfin LAN IP into an ignored `.env`
(or uses `KIDS_LAN_IP` on initial setup), downloads the pinned English Vikidia
archive with pictures, verifies its committed SHA-256, and starts the containers.
Existing content/catalogs are preserved. First setup requires Internet access;
normal play and encyclopedia reading do not. Subsequent deployments verify the
local archive without downloading it again. Images must be cached before a
fully disconnected rebuild. The encyclopedia uses a dedicated internal network;
the portal also joins a dedicated ingress bridge for its LAN-bound port. Neither
joins Cloudflare's `homelab` network. Only the portal publishes a host port.

Open **http://kids.home.arpa/** using Pi-hole DNS. A local A record maps
`kids.home.arpa` to `192.168.4.27`. The shared LAN proxy owns port 80 and routes
Jellyfin's hostname separately. Direct fallback: **http://192.168.4.27:8092/**.
See [LAN proxy deployment and rollback](../lan-proxy/README.md).
No router or Cloudflare changes are needed.

## Encyclopedia

Kiwix 3.8.2 serves `vikidia_en_all_maxi_2026-09.zim` under `/discover/`.
The pinned archive is approximately 74 MB, downloaded from the official Kiwix
mirror redirector; the SHA-256 was checked against its published `.zim.sha256`.
Content stays at `/srv/homelab/media/kids/encyclopedia`, mounted read-only.
Vikidia is intended primarily for ages 8–13; review its topics for your family.
The six-year-old may benefit from reading together. An offline snapshot is not
a content filter: encyclopedia pages can contain external links, and the portal
does not restrict the PC's general Internet access.

To update: select and review a new official archive, update its name and checksum
in `prepare-content.py` and the Compose command, and redeploy. Older archives are
not deleted automatically. Back up the small catalog and any irreplaceable family
ROM files; encyclopedia archives are rebuildable downloads.

## Optional console games

Built-in games work immediately; the console shelf starts empty. No commercial
ROMs are bundled or downloaded. Add parent-selected homebrew or games you have
appropriate rights to use:

1. Download the official EmulatorJS **4.2.3** release from
   https://github.com/EmulatorJS/EmulatorJS/releases/tag/v4.2.3 and extract it so
   `/srv/homelab/media/kids/arcade/emulator/data/loader.js` exists. Retain upstream
   licenses. Include the full `data/` directory and required emulator cores;
   do not configure a CDN fallback. Check each chosen game with WAN disconnected.
2. Place ROMs under `/srv/homelab/media/kids/arcade/roms/`. Use simple filenames.
3. Edit `/srv/homelab/media/kids/arcade/catalog.json`, for example:

```json
[
  {
    "id": "family-adventure",
    "title": "Family Adventure",
    "core": "nes",
    "file": "/arcade/roms/family-adventure.nes",
    "controls": "Arrow keys to move. Check the emulator keyboard menu for action keys."
  }
]
```

Supported shelf identifiers: `nes`, `snes`, `gb`, `gba`, `segaMD`. Choose games
that require no separately licensed BIOS. Check real keyboard mappings before
writing each game's controls card. Catalog changes appear on refresh.

## Operations and rollback

```bash
docker compose -f services/kids/compose.yml ps
docker compose -f services/kids/compose.yml logs --tail 60
curl -f http://192.168.4.27:8092/
curl -fL http://192.168.4.27:8092/discover/
# Stop/remove only these containers; family content remains on disk:
docker compose -f services/kids/compose.yml down
```

Use keyboard navigation to open a game, move with arrows, pause with P, and
restart with Enter. Breakout relaunches with Space without a lives limit. Snake
wraps at the edges. Switch away from a game to pause it automatically. Review
the encyclopedia, drawing export, and games from an actual child PC before use.

## Maker encyclopedia

`http://kids.home.arpa/makers.html` provides 15 original, child-friendly articles
on 3D printing, CAD, slicing, filament, Arduino, Raspberry Pi, Pico, ESP32,
circuits, sensors, motors/robots, coding, networks, servers, and troubleshooting.
Each has a short introduction, expandable deeper reading, vocabulary, a paper
or pretend-play activity, a quiz, and related-topic links. Local demonstrations
show layers, a button/light controller, and a home-network request. They do not
connect to real hardware. Hardware notes direct children to adult supervision.

This is an additional local reference collection alongside Vikidia. It does not
modify the downloaded ZIM or its checksum. Maker search filters this collection;
Vikidia keeps its own full-text search. Both are linked from the discovery room,
and the maker collection also has a home-page tile.

The editable sources are `web/maker-data.json`, `web/makers.html`,
`web/makers.js`, and `web/makers.css`. All runtime resources are local. Articles
were reviewed on 2026-10-26 against the official references linked in each
article's collapsed grown-up section; those optional source websites require
Internet access and are not mirrored or loaded in the background. Text is
original explanatory material rather than copied vendor documentation. The guide
should be reviewed again when adding board-specific electrical instructions.

Run `node --test tests/test_kids_activities.cjs` to check topic references, quizzes,
local runtime assets, and existing activities. Static edits are served from the
read-only bind mount immediately; no encyclopedia download or database migration
is needed. Refresh the browser after deployment. No reading history is stored.
