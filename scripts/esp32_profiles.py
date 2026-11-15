from dataclasses import dataclass


@dataclass(frozen=True)
class Board:
    chip: str
    flash_size: int
    parts: tuple


def flash_parts(boot_offset, app_size):
    return (
        ('bootloader.bin', boot_offset, 0x8000 - boot_offset),
        ('partitions.bin', 0x8000, 0x1000),
        ('boot_app0.bin', 0xE000, 0x2000),
        ('firmware.bin', 0x10000, app_size),
    )


BOARDS = {
    'cyd': Board('esp32', 0x400000, flash_parts(0x1000, 0x140000)),
    'waveshare-s3-touch-169': Board('esp32s3', 0x1000000, flash_parts(0, 0x640000)),
}
