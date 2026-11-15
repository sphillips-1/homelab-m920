# CYD audiobook player

Firmware for the dual-USB **ESP32-2432S028** 2.8-inch touchscreen board from the homelab monitor project. It reads chapter audio from the onboard microSD slot and sends audio to Bluetooth Classic (A2DP) headphones or a Bluetooth speaker.

## Prepare the microSD card

Use a FAT32 card, Python 3, and FFmpeg. The converter takes chapter-split audio from ZIPs, directories, or individual files and writes an Audiobooks folder to the card or a staging folder. Each chapter is converted to signed 16-bit little-endian mono PCM at 22,050 Hz. Budget about 159 MB per hour.

Open PowerShell in this project directory. Replace E: with the microSD drive letter.

```powershell
$downloads = Join-Path $env:USERPROFILE Downloads
$archives = @(
  (Join-Path $downloads 'LibraryItems-1789930742692.zip')
  (Join-Path $downloads 'Chrysalis, Books 1-3 (1).zip')
  (Join-Path $downloads 'Chrysalis, Books 1-3.zip')
)
py -3 -X utf8 tools/prepare_card.py @archives --include B0CS3XXW7C --list
py -3 -X utf8 tools/prepare_card.py @archives --include B0CS3XXW7C --card E:\
```

These three archives together contain all 435 numbered chapters in the box set, including opening and closing credits. The filter selects only this box set from the larger library export. For a quick check, use a separate staging folder with --limit 2. If conversion is interrupted, rerun with the same input set, destination and --resume.

## Deploy from the M920Q

The [ESP32 firmware workflow](../../docs/esp32-deployment.md) deploys this project over USB on the M920Q. The commands below are for a separate Windows bench connection.

## Build and upload locally

Install PlatformIO Core or use the existing local installation. Connect the CYD by USB and identify its COM port from the list before uploading. Substitute the CYD's port for COM5.

```powershell
$pio = "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"
& $pio run
& $pio device list
& $pio run -t upload --upload-port COM5
```


## First playback

1. Insert the prepared card and boot the board.
2. Tap and release the four calibration crosshairs. A two-second press anywhere on the player screen restarts calibration.
3. Put the Sony WH-1000XM5 into pairing mode. Wait for the Pairing message to change to the chapter number, then tap Play. Use −15 sec and +30 sec to seek or Chapters to pick a chapter. Playback advances to the next chapter automatically.
4. Pause, reset, and tap Play to resume. The firmware saves position on pause, seek, chapter changes and every 15 seconds during playback.
5. Turn off the headphones during playback. The player pauses and saves your spot. Turn the headphones back on, wait for reconnection, then tap Play. Try two consecutive chapters to verify automatic advance.

For a different Bluetooth Classic headset or speaker, put a UTF-8 text file named headphones.txt in the root of the microSD card. Enter its advertised Bluetooth name on the first line and restart the CYD with that device in pairing mode. Remove the file and restart to return to WH-1000XM5. The same prepared audio files work with Bluetooth. The display uses the existing monitor's ST7789 configuration on HSPI. MicroSD uses VSPI and touch uses GPIO transfers on its dedicated pins.

- [CYD pin assignments](https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display/blob/main/PINS.md)
- [ESP32-A2DP source library](https://github.com/pschatzmann/ESP32-A2DP/tree/v1.8.8)

## Download from Audiobookshelf

See [M920 download helper setup](../../services/cyd-download/README.md) for Wi-Fi browsing and offline downloads.
