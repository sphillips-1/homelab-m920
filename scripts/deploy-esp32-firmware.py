#!/usr/bin/env python3
"""Flash a checked CI artifact to one identified ESP32, with a private backup."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

PARTS = (('bootloader.bin', 0x1000, 0x7000), ('partitions.bin', 0x8000, 0x1000),
         ('boot_app0.bin', 0xE000, 0x2000), ('firmware.bin', 0x10000, 0x140000))


def validate_artifact(directory, expected_sha):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if not re.fullmatch(r'[0-9a-f]{40}', expected_sha):
        raise ValueError('Invalid expected commit SHA')
    if (manifest.get('schema') != 1 or manifest.get('git_sha') != expected_sha or
            manifest.get('chip') != 'esp32' or manifest.get('flash_size') != 0x400000):
        raise ValueError('Artifact does not match this commit and board profile')
    images = manifest.get('images', [])
    if not isinstance(images, list) or len(images) != len(PARTS):
        raise ValueError('Expected exactly four flash images')
    flash_args = []
    for image, (name, offset, limit) in zip(images, PARTS):
        if image.get('file') != name or image.get('offset') != offset:
            raise ValueError('Unexpected image or offset; refusing to touch device state')
        path = directory / name
        if path.is_symlink():
            raise ValueError('Image symlinks are not allowed')
        data = path.read_bytes()
        if (not 0 < len(data) <= limit or image.get('size') != len(data) or
                image.get('sha256') != hashlib.sha256(data).hexdigest()):
            raise ValueError(f'Artifact integrity check failed: {name}')
        flash_args.extend([hex(offset), str(path)])
    return manifest, flash_args


def esptool(port, *args):
    # Do not print raw serial/device output: it may include private device data.
    result = subprocess.run([sys.executable, '-m', 'esptool', '--chip', 'esp32',
                             '--port', port, '--baud', '460800', *map(str, args)],
                            text=True, capture_output=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f'esptool {args[0]} failed (exit {result.returncode})')
    return result.stdout


def verify_identity(port, expected_mac):
    expected_mac = expected_mac.lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', expected_mac):
        raise ValueError('Invalid expected ESP32 MAC')
    output = esptool(port, 'read-mac')
    found = re.findall(r'MAC:\s*((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})', output)
    if not found or any(mac.lower() != expected_mac for mac in found):
        raise ValueError('Connected ESP32 identity does not match the configured board')


def check_boot(port):
    import serial
    with serial.Serial(port, 115200, timeout=0.3) as connection:
        connection.dtr = False
        connection.rts = True
        time.sleep(0.15)
        connection.rts = False
        deadline = time.monotonic() + 12
        output = bytearray()
        while time.monotonic() < deadline:
            output.extend(connection.read(2048))
        text = output.decode('utf-8', errors='replace')
        if 'entry ' not in text or any(marker in text for marker in
                ('Guru Meditation', 'Brownout', 'abort() was called', 'Backtrace:')):
            raise RuntimeError('Firmware failed the serial boot check')


def deploy(directory, backup_root, port, expected_mac, sha):
    manifest, flash_args = validate_artifact(directory, sha)
    os.umask(0o077)
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # The lock also protects against an operator running two containers at once.
    import fcntl
    with (backup_root / '.flash.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_identity(port, expected_mac)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_dir = backup_root / f'{stamp}-{sha[:12]}'
        backup_dir.mkdir(mode=0o700)
        backup = backup_dir / 'previous-flash.bin'
        print('Backing up complete device flash privately on the M920Q.', flush=True)
        esptool(port, 'read-flash', '0', '0x400000', backup)
        if backup.stat().st_size != 0x400000:
            raise RuntimeError('Incomplete backup; refusing to flash')
        backup_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
        record = dict(git_sha=sha, mac=expected_mac.lower(), backup_sha256=backup_hash,
                      artifact=manifest, status='backed-up')
        record_path = backup_dir / 'deployment.json'
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        try:
            print(f'Flashing commit {sha}; NVS is outside all write ranges.', flush=True)
            esptool(port, 'write-flash', '--flash-mode', 'dio', '--flash-freq', '40m',
                    '--flash-size', '4MB', *flash_args)
            esptool(port, 'verify-flash', *flash_args)
            check_boot(port)
        except Exception:
            print('Deployment failed; restoring the complete pre-flash backup.', flush=True)
            record['status'] = 'failed'
            try:
                verify_identity(port, expected_mac)
                esptool(port, 'write-flash', '0', backup)
                esptool(port, 'verify-flash', '0', backup)
                record['status'] = 'rolled-back'
            except Exception:
                record['status'] = 'rollback-failed'
            record_path.write_text(json.dumps(record, indent=2) + '\n')
            raise
        record['status'] = 'deployed'
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        print(f'Flash verified; boot check passed. Private backup: {backup_dir}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=Path, default=Path('/firmware'))
    parser.add_argument('--backups', type=Path, default=Path('/backups/esp32'))
    parser.add_argument('--port', default='/dev/esp32')
    parser.add_argument('--mac', required=True)
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    deploy(args.artifact, args.backups, args.port, args.mac, args.sha)
