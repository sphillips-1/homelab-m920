# Hardware inventory

Consolidated on 2026-10-31 from repository documentation. This is a record of
documented equipment, not a fresh physical audit. Unknown specifications remain
unconfirmed. Update this file when hardware is added, replaced, or retired.
Maintain LAN addresses in the [network inventory](network-inventory.md).

## Compute and monitoring

| Device | Role and documented configuration | Unconfirmed details |
| --- | --- | --- |
| Lenovo ThinkCentre M920Q | Primary homelab server, hostname `homelab`; Debian 13, Docker, Tailscale; Intel Quick Sync used by Jellyfin | Exact CPU, installed RAM, internal disk model and capacity |
| Raspberry Pi Zero 2 W | Pi-hole DNS server; paired with Geekworm X306 V1.5 UPS and an 18650 battery; identified as Zero 2 W in the owner's enclosure project | microSD model and capacity; installed header/heatsink details |
| Raspberry Pi 4 | Owner-confirmed hardware; existing carrier design targets Model B mechanical layout | Board revision, RAM, current role, cooling hardware, and installed accessories |
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
These are design artifacts; they do not establish that a rack, printed
carrier, or particular printer is currently installed. The carrier guide says
physical fit testing remains outstanding.

## Enclosure design reference

All dimensions below are **millimetres**. PCB outlines exclude projecting plugs,
cables, and accessories. Manufacturer geometry, approximate owner measurements,
and prototype allowances are identified separately; none establishes a completed
physical fit test. Use board-local coordinates, with the origin at the stated
PCB corner, rather than copying coordinates from a rotated tray model.

### Raspberry Pi Zero 2 W with Geekworm X306 V1.5

| Feature | Dimension or design requirement | Evidence |
| --- | --- | --- |
| Bare Pi PCB | 65 × 30; mounting rectangle 58 × 23, centres 3.5 from the corresponding board edges | [Official Zero 2 W mechanical drawing](https://datasheets.raspberrypi.com/rpizero2/raspberry-pi-zero-2-w-mechanical-drawing.pdf) |
| X306 V1.5 PCB | 52 × 78 | Manufacturer DXF, extracted in [mounting research](../hardware/pi-zero-x306-tray/x306-mounting-research.md) |
| X306 mounting centres | (25.5, 3.5), (48.5, 3.5), (25.5, 61.5), (48.5, 61.5) in the DXF coordinate system; rectangle 23 × 58 | Same DXF; pattern is offset toward the Pi side, not centred on the UPS outline |
| Complete Pi/UPS/battery envelope | Approximately 53 × 80 × 25 | Prior owner measurement retained in the enclosure guides; not a precision maximum envelope |
| Battery | One 18650 cell; exact installed cell dimensions/model unrecorded | [Owner's enclosure project](../hardware/pi-zero-x306-skadis-case/README.md); [Geekworm manual](https://wiki.geekworm.com/X306) |
| Underside attachment | M2.5 mounting system; manufacturer case guide uses 6+3 male/female spacers and M2.5 screws | [Manufacturer installation guide](https://wiki.geekworm.com/File:X306-C1-IMG-9759-Install-Guide.jpg) and local mounting research |

Preserve the factory Pi/UPS fasteners and pogo-pin contact. Mount through the
existing underside attachment points, with insulating separation from exposed
components. DXF pad graphics of 3.10 and 4.22 diameter do **not** establish a drill
diameter or thread depth. Measure usable thread engagement before choosing screws.

Provide access to the X306 **USB-C supply input**, power button, and charge/status
LEDs. Also allow access to the Pi's microSD, mini-HDMI, micro-USB OTG, camera
connector, and GPIO if required by the intended use. Measure their positions in
the assembled orientation; the UPS and battery change access relative to a bare
Pi enclosure. Allow battery removal and ventilation without loading the cell,
solder joints, or pogo contacts.

The existing SKÅDIS prototype uses a 22 × 20 USB-C access opening and checks a
nominal 14 × 10 plug body. Those are **case design allowances**, not measured
connector dimensions. Its 6 mm insulating spacers and nominal 3 mm component
clearances are specific to that prototype. The older rack tray's 25 mm height
limit and 0.25 mm passage gaps are also prototype constraints, not universal
assembly clearances.

Still measure: actual maximum assembled height, mounting-plane-to-top and
mounting-plane-to-lowest-component distances, USB-C/button/LED centres, screw
depth, battery extraction path, and any fitted heatsink/header. The 2D X306
drawing does not define these vertical dimensions.

### Raspberry Pi 4

The enclosure basis is the **Model B** layout used by the repository's Pi 4
cartridge. Confirm the installed board marking before finalizing a case.

| Feature | Dimension or design requirement | Evidence |
| --- | --- | --- |
| PCB outline | 85 × 56 | [Official Pi 4 Model B mechanical drawing](https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-mechanical-drawing.pdf) |
| Mounting pattern | Four holes on a 58 × 49 rectangle | Same drawing; also used by the [rack carrier](../hardware/rack-carrier/README.md) |
| Fastener basis | M2.5 clearance mounting; keep screw heads below slide surfaces if reusing the cartridge | Existing carrier design; verify length against the actual stack |
| Existing carrier standoffs | 5 mm tall | Prototype design value, not PCB/component height |

Keep the Ethernet and stacked USB connectors accessible on the end edge, and
USB-C power, both micro-HDMI connectors, and the audio jack accessible along the
side. Include underside microSD access. Reserve GPIO, camera and display ribbon
cable paths when needed. Use the official drawing for connector placement; the
85 × 56 outline does not include all connector overhangs or inserted plugs.

Measure the actual top/bottom component envelopes, fitted heatsink/fan/HAT,
connector protrusions, plug bodies, and cable bends before selecting internal
height or cutout sizes. Provide intake/exhaust paths for the installed cooling
arrangement. The carrier's compact right-angle USB-C suggestion is a layout
constraint, not confirmation that every right-angle plug fits.

### ESP32-2432S028 dual-USB display

Identity is supported by the photographed board and firmware guide:
ESP32-D0WD-V3 revision 3.1, 4 MB flash, ST7789 profile, 320 × 240 landscape.
Pixel resolution does **not** specify the physical display aperture. Similar
ESP32-2432S028 boards have different panel and connector layouts; a generic ESP32
DevKit or single-USB case is not a verified mechanical match.

No dimensioned drawing or caliper measurements for this exact board revision
are recorded. Before making a fitted case, record:

| Measurement | Needed for |
| --- | --- |
| PCB length, width, thickness, corner shape | Internal footprint and edge supports |
| All mounting-hole centres, diameters, and edge offsets | Standoffs and screw selection; do not assume a Pi hole pattern |
| PCB-to-display-front height and maximum rear component height | Case depth and bezel seating |
| Active display and outer glass dimensions/offsets | Bezel opening without pressure on the glass or touch area |
| Both USB connector types, locations, heights, and projecting plug bodies | Power/programming cutouts and cable clearance |
| BOOT and RST locations and travel | Recessed access or button actuators; BOOT is used for Wi-Fi setup |
| microSD and any fitted expansion connectors | Card extraction and optional wiring access |
| Antenna location and rear component keep-outs | Clear space around the antenna and electronics |

Retain power/programming access, avoid clamping the display glass, and leave
space for cable strain relief. See the [firmware guide](../hardware/esp32-monitor/README.md)
for the verified board identity and button behavior. Mechanical values remain
unconfirmed until measured on this dual-USB unit.

### Print-fit checks

Keep device dimensions separate from configurable print clearances. Test a
mounting/cutout coupon with the actual printer, material, fasteners, inserts,
and cables before a full enclosure. Include the floor, spacers, lid, screw
heads, and installed plugs in the stack and insertion/removal envelope. Print
in millimetres at 100% scale; adjust clearances in CAD rather than scaling hole
spacing. Physical fit and operating temperature still require checking.

## Maintenance

- Record exact CPU, RAM, disk, battery, and board specifications when confirmed.
- Record a device's role and installation/retirement status separately from designs or purchase plans.
- Keep credentials, application databases, generated metadata, and runtime state outside Git.
- Update the network inventory when an address changes rather than duplicating addresses here.
