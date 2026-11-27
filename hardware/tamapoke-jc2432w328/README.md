# TamaPoke hardware port for the Ant CYD

The Ant CYD was identified on Windows COM5 by factory MAC
`68:09:47:85:c6:d8`. It reports an ESP32-D0WD-V3 rev 3.1 with 4 MB of flash.
The board profile comes from the repository's existing JC2432W328 firmware.
Guition sells capacitive, resistive and no-touch variants of this display.
The Ant CYD's touch variant still needs physical confirmation.

The port applies to a pinned upstream TamaPoke checkout. It centers the
466 × 466 logical UI on the ST7789 as a 233 × 233 RGB565 framebuffer in internal
RAM. The two build environments cover CST820 capacitive touch and XPT2046
resistive touch. Resistive raw touch bounds are initial estimates and need
calibration on hardware.

The microSD card uses the board's second SPI bus. For optional sprites, use a
FAT32 card with the upstream `tools/sdcard/mons` directory copied to the card
root. If a sprite cannot fit in available RAM, TamaPoke uses a built-in sprite when available. Audio, battery measurement and
battery-backed time are unavailable in this profile. The running clock uses the
ESP32's software clock.

## Build

From the repository root in PowerShell with Git and PlatformIO installed:

```powershell
$checkout = Join-Path $env:TEMP 'TamaPoke-JC2432W328'
./hardware/tamapoke-jc2432w328/prepare.ps1 -Checkout $checkout
pio run -d $checkout -e jc2432w328c
pio run -d $checkout -e jc2432w328r
```

## Deploy Ant over Wi-Fi

Both builds use Shelf Ant's existing 4 MB dual-OTA partition table. TamaPoke
uses the existing Wi-Fi station settings and authenticated OTA key stored in
NVS. It keeps listening for later updates after it boots and reconnects.

Once the workflow is on main, run **Actions → TamaPoke Ant OTA → Run workflow**.
Select `jc2432w328c` for CST820 or `jc2432w328r` for XPT2046. The M920Q runner
checks Ant's MAC and uses the existing `CYD_ANT_OTA_HOST` variable and
`CYD_ANT_OTA_KEY` secret. The upload writes only the app into the inactive
OTA slot. The existing **ESP32 firmware** workflow can reinstall Shelf Ant
using the Ant OTA target.
This port adapts TamaPoke by socquique and contributors under CC BY-NC-SA 4.0. See the [upstream license](https://github.com/socquique/TamaPoke/blob/a441be28270b6d48cc922454df11618fe04d1e45/LICENSE) and [sprite credits](https://github.com/socquique/TamaPoke/blob/a441be28270b6d48cc922454df11618fe04d1e45/CREDITS.md).
[Guition board package](https://components.espressif.com/components/guition/guition_boards/versions/0.2.4/readme)
