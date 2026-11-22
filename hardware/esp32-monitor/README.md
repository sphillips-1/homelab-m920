# Shelf Goblin on Waveshare ESP32-S3

The Waveshare ESP32-S3-Touch-LCD-1.69 runs the Shelf Goblin virtual pet. Its
evolutions use XP earned from fights and time on the pet screen. The pet works
offline and saves progress on the board. The neighboring
[CYD status display](../cyd-status/README.md) monitors the M920Q and can join
Goblin fights and patrols over ESP-NOW.

## Setup and controls

This panel uses BGR channel order. Keep `TFT_RGB_ORDER=TFT_BGR` so red and blue render correctly.

The Waveshare target runs Shelf Goblin offline in portrait and landscape. The onboard
accelerometer rotates the display and touch together when the board settles
in a new orientation. The current orientation is retained when laid flat.
Build with `pio run -d hardware/esp32-monitor -e waveshare-s3-touch-169`.
Use the [M920 USB deployment workflow](../../docs/esp32-deployment.md) to flash
the connected board. Use USB-C power for bench testing. Follow the prompts if touch calibration is
needed. Hold BOOT for one second and release to recalibrate.

## XP and evolutions

Tap **FIGHT!**. A win earns 20, 25, or 35 XP against a lower-, equal-,
or higher-level opponent. A defeat deducts the same amount, down to 0 XP.
If XP falls below the current level's threshold, the goblin devolves to the
form for its remaining XP.
The goblin also earns 1 XP for every five uninterrupted minutes on the pet
screen while powered on. Battles and touch calibration restart the idle timer.
XP changes are saved in NVS. A board without saved XP starts at level 1 with 0 XP.

| Level | Form | Total XP |
| --- | --- | ---: |
| 1 | Baby Goblin | 0 |
| 2 | Scavenger | 60 |
| 3 | Adult Goblin | 150 |
| 4 | Tactician | 280 |
| 5 | Red Hobgoblin | 460 |
| 6 | Chieftain | 700 |
| 7 | Great Chieftain | 1,010 |
| 8 | Goblin Lord | 1,400 |
| 9 | Goblin King | 1,900 |

## Paired rack displays

With the Waveshare mounted to the left of the CYD, a fight shows the Goblin on
the Waveshare and its opponent on the CYD. Both animate the clash using the
Waveshare's fight clock. XP and combat results are still owned by the Waveshare.

When the CYD is available, the Goblin takes a patrol every three to seven minutes
of scheduled time, waiting for any fight or touch setup to finish. He walks
across the shared edge, inspects the condensed CYD metrics for seven seconds,
then walks home. The Waveshare shows an **out on patrol** sign during the visit.

The two boards exchange short ESP-NOW messages addressed to the documented
station MACs in `src/display_link.h`. The Waveshare searches channels 1 through 11
for the CYD's heartbeat and follows the CYD's Wi-Fi channel. The Waveshare
needs no Wi-Fi credentials. If the CYD is unavailable, fights play on the
Waveshare and patrols wait. The CYD automatically returns to its selected
Metrics or Camp page when an animation finishes or its updates expire.

Build and flash both targets through the **ESP32 firmware** GitHub Actions
workflow to activate pairing. Select `waveshare-s3-touch-169` and `cyd` in
separate runs on `main`. Update both firmware images if either board's station
MAC changes.

## Build validation

The **ESP32 firmware** GitHub Actions workflow builds and packages the Waveshare
pet and the CYD status display and runs the portable firmware and deployment
tests. Use the [USB deployment guide](../../docs/esp32-deployment.md) for
board selection, backup, and recovery. Verify the screen, touch, and orientation
on the physical board after deployment.

The [legacy CYD Goblin guide](legacy-cyd.md) covers the local health-based build.

## Cat and Ant virtual pets

The two pets use the same Waveshare ESP32-S3-Touch-LCD-1.69 profile as the
Goblin. Build them with PlatformIO from the repository root:

```sh
pio run -d hardware/esp32-monitor -e waveshare-cat -e waveshare-ant
```

Tap **POUNCE!** to chase a toy as the Cat or **CHALLENGE!** to face a tunnel
creature as the Ant. Wins earn 20, 25, or 35 XP against lower, equal, or
higher levels. Losses subtract the same amount, and five uninterrupted idle
minutes earn 1 XP. Each pet has a starter and ten evolved forms, with the
final two thresholds at 2,500 and 3,200 XP. The screen shows the current
form, progress toward the next form, and the best form reached. Each pet
saves its own XP, best form, and touch calibration locally and plays offline.

GitHub Actions compiles both pet targets. Flashing them through the M920
workflow requires registering the two USB devices as deployment targets once
the board models and identities are confirmed.

### Nearby visits

An idle Waveshare pet can automatically visit another reachable idle pet or
the CYD camp. After startup, pets begin looking for a visit after 15–35
seconds. After a visit, they wait one to two minutes before starting another.
A pet-to-pet visit lasts about eight seconds. Tap **Come Home** or **End
Visit** to end it early. Each pet keeps its own XP and evolution progress.

Visits use ESP-NOW directly between the boards. The Cat and Ant can find each
other on channel 6 when the Goblin is away. They periodically search for the
Goblin and share its channel once found, including when the Goblin is linked
to the CYD. Give discovery a few seconds after powering on or moving a pet
back into range. If either board drops out during a visit, the other goes
back home automatically.

Pets that choose [Group Camp on the CYD](../cyd-status/README.md#group-camp)
stay for 25–45 seconds before returning home.
