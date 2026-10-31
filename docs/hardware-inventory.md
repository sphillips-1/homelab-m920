# Hardware inventory

Consolidated on 2026-10-31 from repository documentation. This is a record of
documented equipment, not a fresh physical audit. Unknown specifications remain
unconfirmed. Update this file when hardware is added, replaced, or retired.
Maintain LAN addresses in the [network inventory](network-inventory.md).

## Compute and monitoring

| Device | Role and documented configuration | Unconfirmed details |
| --- | --- | --- |
| Lenovo ThinkCentre M920Q | Primary homelab server, hostname `homelab`; Debian 13, Docker, Tailscale; Intel Quick Sync used by Jellyfin | Exact CPU, installed RAM, internal disk model and capacity |
| Raspberry Pi Zero 2 | Pi-hole DNS server; paired with Geekworm X306 V1.5 UPS | RAM/storage details, microSD model and capacity; exact board variant |
| ESP32-2432S028 dual-USB display | M920Q desk status monitor; ESP32-D0WD-V3 revision 3.1, 4 MB flash; firmware uses ST7789 panel profile | Separate battery/UPS installation |

Sources: [repository overview](../README.md),
[network inventory](network-inventory.md), and
[display firmware guide](../hardware/esp32-monitor/README.md).
The display's COM3 reference is a historical flashing port, not a permanent
device identifier.

## Power

| Device | Associated equipment | Documented status |
| --- | --- | --- |
| Geekworm X306 V1.5 5V UPS expansion board | Pi Zero 2 / Pi-hole | Model confirmed by owner on 2026-10-16; battery model and capacity unrecorded |

The X306's documented indicators do not provide a software-readable power-loss
or battery telemetry interface. Battery-mode monitoring is not deployed; see
the [UPS notes](network-inventory.md#pi-zero-battery-backup).

## Storage

| Device | Purpose and mount | Documented configuration |
| --- | --- | --- |
| M920Q internal disk | Operating system, rebuildable infrastructure under `/opt/homelab`, application state under `/srv/homelab/appdata` | Model, interface, and capacity unrecorded |
| External media drive | Media filesystem at `/srv/homelab/storage`; bind mounts beneath `/srv/homelab/media` | Model, capacity, and connection details unrecorded |
| Dedicated torrent USB device | Complete and incomplete downloads at `/srv/homelab/media/torrents-m920` | 116 GiB ext4 filesystem, label `AUDIOBOOKS`; filesystem UUID `e440863e-34ce-4c29-b05a-c5dfda01a743` |

The 116 GiB value describes the documented filesystem, not a confirmed marketed
device capacity. Sources: [storage layout](storage.md) and
[torrent storage guide](../services/qbittorrent-m920/README.md#dedicated-torrent-usb).

## Mounting and fabrication

The repository contains a [Lab Rax three-bay carrier prototype](../hardware/rack-carrier/README.md)
with Pi 4 and Zero/X306 cartridges, plus
[Pi Zero/X306 tray designs](../hardware/pi-zero-x306-tray/README.md).
These are design artifacts; they do not establish that a Pi 4, rack, printed
carrier, or particular printer is currently installed. The carrier guide says
physical fit testing remains outstanding.

## Maintenance

- Record exact CPU, RAM, disk, battery, and board specifications when confirmed.
- Record a device's role and installation/retirement status separately from designs or purchase plans.
- Keep credentials, application databases, generated metadata, and runtime state outside Git.
- Update the network inventory when an address changes rather than duplicating addresses here.
