# ESP32 USB deployment through GitHub Actions

The existing `self-hosted`, `linux`, `x64`, `m920` runner flashes the
connected display over USB. GitHub-hosted runners build and test the
[Waveshare Shelf Goblin](../hardware/esp32-monitor/README.md) and
[CYD M920Q status display](../hardware/cyd-status/README.md).

## Run a deployment

Firmware and deployment changes pushed to main deploy the Waveshare by
default. Pushes that change the CYD status project without changing the
monitor project deploy the CYD. To deploy manually, open the **ESP32 firmware** workflow
in GitHub Actions, select **Run workflow** on **main**, and choose
`waveshare-s3-touch-169` or `cyd`. Pull requests and pushes to other branches
build and package both targets. Deployment uses the existing `infrastructure`
environment and approval policy. Deployments run one at a time and reject
builds that predate a newer firmware change on main.

The runner downloads the selected board's artifact from the same run. The
manifest identifies its chip, flash size, offsets, checksums and source commit.
The workflow verifies those fields before accessing USB.

## Device binding

| Target | USB by-id basename | MAC | Flash |
| --- | --- | --- | --- |
| Waveshare ESP32-S3 (observed November 15, 2026) | `usb-Espressif_USB_JTAG_serial_debug_unit_28:84:85:55:4C:1C-if00` | `28:84:85:55:4c:1c` | 16 MB |
| CYD (observed November 5, 2026) | `usb-1a86_USB_Serial-if00-port0` | `48:9d:31:c0:27:5c` | 4 MB |

To replace a board, set the repository variables `WAVESHARE_SERIAL_DEVICE`
and `WAVESHARE_MAC` for the Waveshare or `ESP32_SERIAL_DEVICE` and
`ESP32_MAC` for the CYD. Set the serial variable to the full
`/dev/serial/by-id/...` path. The flasher checks the chip and MAC before
backing up or writing.

Both targets use a network-disabled Docker flasher with esptool 5.6.0. The
CYD receives its USB UART device directly. The Waveshare uses its stable
by-id link through a read-only host device mount with a device cgroup rule
limited to ACM serial devices. The link follows the same USB identity if
Linux changes its tty number during a reset.

## Preservation and recovery

Before every flash, the job reads the complete device flash (16 MB for Waveshare, 4 MB for CYD) to:

`/srv/homelab/backups/esp32/<UTC timestamp>-<commit>/previous-flash.bin`

Directories and files are private to root (0700/0600). Flash backups can contain
Wi-Fi credentials. They are never committed, logged, or uploaded to Actions.
Keep them within the homelab's private backup and retention policy; the workflow
does not delete old backups. Each uses approximately the size of the device flash. A neighboring
`deployment.json` records the backup checksum, target manifest and result.

Writes cover the bootloader, partition table, OTA boot selector and app0 only.
The NVS range `0x9000–0xDFFF` is preserved, including Wi-Fi, touch calibration
and health-based evolution progress. A repeat deployment preserves those settings. Retired care
meter data may remain in NVS but is no longer read or updated by the firmware.
The job verifies the written images and checks serial output for known crash
markers. The Waveshare reports that its firmware loop is running, and the CYD
reports ROM boot entry. Physical screen and touch checks are done at the device.

On a flash, verification or boot-check failure, the job attempts to restore and
verify the full pre-flash image, then still fails the Actions run. The record
distinguishes `rolled-back` from `rollback-failed`. A cable disconnect, power
loss, forced cancellation or runner failure can interrupt both flashing and
recovery. Reconnect the device and rerun Actions. If auto-reset cannot enter the
bootloader, physical BOOT/reset assistance may be necessary. Preserve the
private backup for recovery. Never expose the serial port publicly.
