# CYD M920Q status display

The ESP32-2432S028 shows the M920Q's health, CPU utilization and temperature,
memory and disk usage, Docker container counts, uptime, and Wi-Fi signal on a
single landscape screen. It polls the LAN status feed at
`http://192.168.4.27:8091/status` every five seconds. Unavailable readings
show as `--`. If the feed or Wi-Fi drops, the display clears the old readings
and shows Offline.

Deploy the `cyd` target through [ESP32 firmware in GitHub Actions](../../docs/esp32-deployment.md).
Existing Wi-Fi credentials survive the flash. To change Wi-Fi, hold BOOT for
five seconds, join **M920-Display**, and open `http://192.168.4.1` on your phone
or computer.

Build locally with `pio run -d hardware/cyd-status -e cyd`.
