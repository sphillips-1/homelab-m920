# Shelf Goblin and M920Q status on the CYD

The ESP32-2432S028 shows the M920Q's health, CPU utilization and temperature,
memory and disk usage, Docker container counts, uptime, and Wi-Fi signal on a
single landscape screen. It polls the LAN status feed at
`http://192.168.4.27:8091/status` every five seconds. Unavailable readings
show as `--`. If the feed or Wi-Fi drops, the display clears the old readings
and shows Offline.

When paired with the Waveshare Shelf Goblin over ESP-NOW, the CYD can show
the Goblin's opponent during fights and host the Goblin during patrols. The
selected page returns when the animation ends. The Waveshare saves
the pet's XP and determines fight outcomes. See [paired rack displays](../esp32-monitor/README.md#paired-rack-displays).

## Shelf Goblin

The CYD opens to its own Shelf Goblin at startup. Tap the pet screen to fight
and use a short BOOT press to cycle through Goblin, Metrics, and Group Camp.
From Metrics or Camp, tap to return to Goblin. Hold BOOT for five seconds for
Wi-Fi setup.

The CYD uses the same nine forms and battle XP rules as the Waveshare Goblin.
Wins earn XP, defeats deduct XP, and every five uninterrupted minutes on the
Goblin page earns 1 XP. The CYD saves its own XP in NVS and local battles work
offline. The Waveshare keeps its own progress.

Cat and Ant are deployed separately as eggs. See the
[Cat and Ant controls](../../docs/esp32-deployment.md#cat-and-ant-pet-controls).
Their eleven forms, artwork, opponents, and saves are specific to each pet.

## Group Camp

Group Camp remains available through the BOOT page cycle. Linked Waveshare
fights and patrols can briefly use the display and then return to the selected
page. A local CYD fight takes priority.

Nearby idle pets visit automatically and stay for 25–45 seconds. Up to three
pets can stay at once. The CYD shows each guest's current form. Tap
**Come Home** on the pet to end its visit. A lost radio link clears the
visitor and returns the pet to its own screen within about seven seconds.
XP remains on each pet.

Camp uses ESP-NOW on the CYD's current radio channel. The pet boards can join
without storing Wi-Fi credentials.

Deploy the `cyd` target through [ESP32 firmware in GitHub Actions](../../docs/esp32-deployment.md).
Existing Wi-Fi credentials survive the flash. To change Wi-Fi, hold BOOT for
five seconds, join **M920-Display**, and open `http://192.168.4.1` on your phone
or computer.

Build locally with `pio run -d hardware/cyd-status -e cyd`.
