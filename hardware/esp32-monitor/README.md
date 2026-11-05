# Shelf Goblin homelab companion

Firmware for the photographed ESP32-2432S028 dual-USB board, now USB-connected
to the M920Q for power and GitHub Actions deployment:
ESP32-D0WD-V3 revision 3.1, 4 MB flash. Uses the ST7789 panel profile at
320×240 landscape. Some visually similar boards use ILI9342: a successful
flash alone does not verify panel compatibility. Confirm the screen visually.
This panel uses `TFT_INVERSION_OFF`: enabling inversion made the green goblin
appear pink on the owner's display. Keep inversion disabled for this board.

## Setup

Normal deployments run through **Actions → ESP32 firmware** on **main**, or
automatically after firmware changes reach main. The existing homelab runner
identifies the connected board, saves a private full-flash backup, flashes the
checksummed CI artifact and checks startup. See [USB deployment and
recovery](../../docs/esp32-deployment.md). Wi-Fi and pet progress are preserved.

The following local commands are historical bench/recovery references. COM3
was its Windows connection before it moved to the homelab; normal updates now
use the Actions workflow.

1. Install the server feed described in [the service guide](../../services/esp32-monitor/README.md).
2. Install PlatformIO 6.2.0, then run `pio run -d hardware/esp32-monitor`.
3. Before flashing, use esptool to read the complete 4 MB flash to a private,
   ignored backup: `esptool --port COM3 read-flash 0 0x400000 original.bin`.
   This may contain previous Wi-Fi credentials; do not commit or share it.
4. Flash with `pio run -d hardware/esp32-monitor -t upload --upload-port COM3`.
5. Join **M920-Display** from a phone or laptop and open `http://192.168.4.1`.
   Select the home 2.4 GHz Wi-Fi and enter its password. Credentials persist
   only in the ESP32's NVS, not in the source code. The temporary setup AP has
   no password; perform setup locally and it closes after connection.

## Pet and controls

A code-drawn pixel goblin blinks and bobs while watching the homelab. Short
BOOT presses cycle **Home → Feed → Play → Metrics**. On Feed or Play, hold
BOOT for at least one second and release before five seconds to perform the
action. Feeding produces a short munch animation and snack; playing produces
a sparkle. Both show a response message and share a 30-second cooldown.
There are no Fullness or Happiness meters, hidden needs, or care decay.
Interactions do not change evolution or clear server alerts.

### Health-based evolution

| Accumulated health time | Form |
| --- | --- |
| Less than 1 day | Green baby goblin: big head, small body and diaper |
| 1 day to less than 7 days | Green adult goblin: taller body, tunic and scarf |
| 7 days or more | Red warrior hobgoblin: helmet, armor, tusks, sword and shield |

Healthy and Busy observations earn one second of health time per observed
second. Warning conditions drain one second per second; Critical conditions
drain four. Crossing the same thresholds downward devolves the pet. The bank
is capped at 14 days, allowing a mature warrior to build a week's buffer.
The current bank and time to the next form appear beside the pet.

Unknown, Offline, Wi-Fi setup, repeated sample timestamps and observation gaps
over 20 seconds pause progress. The first fresh observation after a pause only
establishes a baseline. Intervals touching an alert use the worse of their two
endpoint severities. The firmware cannot establish health while unplugged, so
that time earns nothing and incurs no penalty. Host uptime is never treated as
proof of historical health. Existing health-time progress is preserved across
updates. Old feed/play points and retired care meters are not used.

Health time persists in the existing ESP32 NVS key every five minutes and
immediately on evolution/devolution. A sudden power loss can roll
back up to five minutes of progress or decay. Colors describe the creature's
form; an adult or warrior keeps its skin color during Unknown/Offline status,
with the health label conveying connection and server status separately.

Expressions reflect homelab health and brief interactions. No pet state is
sent to the server, and Wi-Fi credentials remain separate from evolution state.

Hold BOOT for five seconds to reopen Wi-Fi setup. This does not also feed or
play. RST reboots the device. Touch navigation is not configured. HTTP requests
are bounded but synchronous, so presses during a request may be missed; hold
the button until the device responds when the network is slow.

## Homelab health

The health label and highest-priority reason remain visible on every page.
Care cannot dismiss a server alert. Metrics refresh every five seconds; failed
requests clear readings and show Offline. Partial responses show Unknown unless
a known reading already establishes an alert. Missing values display `--`.

| Signal | Warning | Alert |
| --- | --- | --- |
| CPU temperature | ≥70°C | ≥85°C |
| RAM, system disk or media disk use | ≥85% | ≥95% |
| Unhealthy containers | — | One or more |

CPU utilization ≥85% is **Busy**, not a fault. Stopped containers can be
intentional and do not trigger an alarm. The Metrics page shows running/total
and unhealthy counts, uptime and Wi-Fi signal. These are M920Q host/container
signals, not application-level probes or Pi-hole health checks. Temperature
thresholds are conservative display defaults, not hardware shutdown controls.

## Build validation

The **ESP32 firmware** GitHub Actions workflow compiles the firmware, checks
health thresholds and evolution timelines, tests deployment failure behavior,
and uploads binaries tied to the commit. Its main-branch deployment job flashes
the connected board through the M920Q runner. Other branches and PRs build only.

The portable health regression test can also be checked locally with
`g++ -std=c++14 tests/test_esp32_health.cpp -o test-esp32-health` from the repo
root, then run the resulting executable. Compile-time assertions can be checked
alone with `g++ -std=c++14 -fsyntax-only tests/test_esp32_health.cpp`.
The UI, NVS persistence, button timing and panel output still require physical
device verification after an approved firmware installation.

The server URL in `src/main.cpp` follows the network inventory. Update that
URL and `MONITOR_BIND` on the server if its address changes, then rebuild.
No OTA update or remote server-control functionality is enabled.

## Recovery

Restore the private backup with
`esptool --port COM3 write-flash 0 original.bin`.
Build output, local tools, and `.esp32-backups/` are ignored by Git.

On Windows, long repository paths can exceed the compiler's internal command
length limit. This installation built successfully using a temporary `H:`
mapping to the repository (`subst H: <repository-path>`), with
`PLATFORMIO_CORE_DIR=H:\.platformio` and project path `H:/hardware/esp32-monitor`.
Release the mapping afterward with `subst H: /d`.

Panel references: [ESPHome CYD profiles](https://github.com/esphome/esphome/blob/dev/esphome/components/mipi_spi/models/cyd.py),
[TFT_eSPI](https://github.com/Bodmer/TFT_eSPI),
[WiFiManager](https://github.com/tzapu/WiFiManager).
