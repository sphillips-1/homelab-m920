# Download Audiobookshelf books to the CYD

The CYD browses the M920 download helper over 2.4 GHz Wi-Fi. The helper reads
the Audiobookshelf catalog and converts AAC, MP3 and other supported audio on
the M920. The CYD saves complete books in /Downloads on its FAT32 microSD card
and plays them offline through Bluetooth. Books already in /Audiobooks remain
available in the device's Books menu.

## Deploy the helper

1. In Audiobookshelf, create a dedicated API key for a user with permission to
   access and download the audiobook libraries you want.
2. Save the key as CYD_ABS_API_KEY in the homelab repository's infrastructure
   GitHub Actions environment. The helper reaches Audiobookshelf over the
   existing homelab Docker network.
3. Run **CYD audiobook downloads** from main and approve the infrastructure
   deployment. The runner verifies that the helper can list the audiobook libraries.
   The endpoint is http://192.168.4.27:8784 on the trusted home LAN.
4. Retrieve the separately generated device token into a private local file.
   For example, with Docker access on the M920, run the following from Windows.
   Keep the destination out of Git.

```powershell
$token = Join-Path $env:LOCALAPPDATA 'CYD-Audiobook\cyd-token.txt'
ssh sean@192.168.4.27 docker exec cyd-download cat /cache/cyd-token.txt |
    Set-Content -LiteralPath $token
```

The helper's cache and token live under /srv/homelab/appdata/cyd-download.
The helper publishes only on the M920's LAN address and uses a separate bearer
token for device requests. Device-to-helper HTTP is for the trusted home LAN.

## Configure the player

Install the Wi-Fi build. It uses a 3 MB application partition with the same
NVS offsets as the original player, so flash the partition table along with the
app. Previous Bluetooth pairing, touch calibration and playback bookmark can
carry over. The card keeps its existing contents.

Mount the microSD card on the PC. From hardware/esp32-audiobook, substitute its
drive for D: and run:

```powershell
$python = "$env:USERPROFILE\.platformio\penv\Scripts\python.exe"
& $python tools/configure_network.py D:\ --host http://192.168.4.27:8784 --token-file $token
```

The prompt saves Wi-Fi details and the helper token in network.txt on the card.
Treat that file as private. The Audiobookshelf API key stays on the M920.

Eject the card, insert it in the CYD, and restart. Choose **Chapters → Books →
Server**, pick a library and book, then select **Download book**. A download
keeps finished parts if interrupted. Select the same book to resume. When it
finishes, select **On microSD** and open the book. The card needs about 159 MB
per hour of audio. The helper uses sequential parts of up to about 15 minutes
for long source files so they fit comfortably on FAT32.
