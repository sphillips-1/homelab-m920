# ESP32 USB deployment through GitHub Actions

The Shelf Goblin is powered and connected by USB to the M920Q. The existing
`self-hosted`, `linux`, `x64`, `m920` runner flashes it locally. GitHub-hosted
runners build and test; no public serial bridge, OTA endpoint, SSH deployment,
new runner, serial-group change or additional sudo rule is required.

## Run a deployment

Push firmware or deployment changes to `main`, or open **Actions → ESP32 firmware
→ Run workflow**, select **main**, and run it. Pull requests and other branches
only build/test and publish firmware artifacts. Deployment uses the existing
`infrastructure` environment and its approval policy. The USB deployment job is
serialized and never cancels a flash to start a newer one. Before flashing it
rejects a build that predates a firmware change already merged into main.

The workflow packages the four flash images plus a manifest containing their
offsets, lengths, SHA-256 checksums and exact Git commit. The deployment job
downloads the artifact from its own build and validates that commit before USB
access. It does not build or flash from `/opt/homelab`, update that checkout,
restart services, or run the Terraform/container deployment pipeline itself.

## Device binding

Observed on November 5, 2026:

- USB by-id: `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
- Current target: `/dev/ttyUSB0` (do not depend on this name remaining stable)
- ESP32 MAC: `48:9d:31:c0:27:5c`
- ESP32-D0WD-V3, 4 MB flash; ST7789 display, inversion disabled.

The workflow defaults to that by-id path and MAC. Repository variables
`ESP32_SERIAL_DEVICE` and `ESP32_MAC` can override them after a verified hardware
change. The MAC must match before any flash backup or write; the generic USB
adapter by-id string alone is not a unique identity. A missing cable, device,
Docker permission or mismatched MAC fails the job rather than selecting another
serial port. Use the board's data-capable USB connection.

The runner account currently has Docker access but lacks serial read/write
permission. A small image installs pinned esptool 5.6.0, then runs with only the
selected USB character device, read-only firmware, and the backup mount. During
flashing it has no network, dropped capabilities, no privilege escalation, a
read-only root filesystem and temporary `/tmp`. Python dependencies live in
the rebuildable image; device state stays on the ESP32 and in private backups.

## Preservation and recovery

Before every flash, the job reads the complete 4 MB device flash to:

`/srv/homelab/backups/esp32/<UTC timestamp>-<commit>/previous-flash.bin`

Directories and files are private to root (0700/0600). Flash backups can contain
Wi-Fi credentials. They are never committed, logged, or uploaded to Actions.
Keep them within the homelab's private backup and retention policy; the workflow
does not delete old backups. Each uses about 4 MB. A neighboring
`deployment.json` records the backup checksum, target manifest and result.

Writes cover the bootloader, partition table, OTA boot selector and app0 only.
The NVS range `0x9000–0xDFFF` is preserved, including Wi-Fi, touch calibration
and health-based evolution progress. A repeat deployment preserves those settings. Retired care
meter data may remain in NVS but is no longer read or updated by the firmware.
Firmware image verification and a 12-second serial boot check must pass before
the job reports success. This checks for boot entry and known crash markers;
it does not confirm the physical screen or end-to-end homelab metrics.

On a flash, verification or boot-check failure, the job attempts to restore and
verify the full pre-flash image, then still fails the Actions run. The record
distinguishes `rolled-back` from `rollback-failed`. A cable disconnect, power
loss, forced cancellation or runner failure can interrupt both flashing and
recovery. Reconnect the device and rerun Actions. If auto-reset cannot enter the
bootloader, physical BOOT/reset assistance may be necessary. Preserve the
private backup for recovery. Never expose the serial port publicly.
