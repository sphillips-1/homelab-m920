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

Open **http://192.168.4.27:8092/**. Port 80 already belongs to Jellyfin.
An optional Pi-hole A record `kids.home.arpa` → `192.168.4.27` gives
**http://kids.home.arpa:8092/**; DNS alone cannot remove the port. Do not change
Jellyfin's port mapping to obtain a portless kids URL without planning a shared proxy.
The record is not automatically installed. No router or Cloudflare changes are needed.

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
