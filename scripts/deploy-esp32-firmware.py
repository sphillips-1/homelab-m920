#!/usr/bin/env python3
"""Deploy a checked CI artifact over USB or authenticated CYD LAN OTA."""
import argparse
from datetime import datetime, timezone
import hashlib
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import re
import runpy
import socket
import stat
import subprocess
import sys
import time

from esp32_profiles import BOARDS

PARTS = BOARDS['cyd'].parts


def validate_artifact(directory, expected_sha, target='cyd'):
    board = BOARDS[target]
    manifest = json.loads((directory / 'manifest.json').read_text())
    if not re.fullmatch(r'[0-9a-f]{40}', expected_sha):
        raise ValueError('Invalid expected commit SHA')
    if (manifest.get('schema') != 1 or manifest.get('git_sha') != expected_sha or
            manifest.get('target') != target or
            manifest.get('chip') != board.chip or manifest.get('flash_size') != board.flash_size):
        raise ValueError('Artifact does not match this commit and board profile')
    images = manifest.get('images', [])
    if not isinstance(images, list) or len(images) != len(board.parts):
        raise ValueError('Expected exactly four flash images')
    flash_args = []
    for image, (name, offset, limit) in zip(images, board.parts):
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


def wait_for_acm(port):
    # The native USB controller can re-enumerate when switching boot modes.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            device = os.stat(port)
            if stat.S_ISCHR(device.st_mode) and os.major(device.st_rdev) == 166:
                return
        except FileNotFoundError:
            pass
        time.sleep(0.2)
    raise RuntimeError('Configured ESP32-S3 USB serial device is unavailable')


def esptool(port, *args, chip='esp32'):
    reset_args = ()
    if chip == 'esp32s3':
        wait_for_acm(port)
        reset_args = ('--before', 'usb-reset')
    # Do not print raw serial/device output: it may include private device data.
    result = subprocess.run([sys.executable, '-m', 'esptool', '--chip', chip,
                             '--port', port, '--baud', '460800', *reset_args, *map(str, args)],
                            text=True, capture_output=True, timeout=600)
    if result.returncode:
        raise RuntimeError(f'esptool {args[0]} failed (exit {result.returncode})')
    return result.stdout


def verify_identity(tool, port, expected_mac):
    expected_mac = expected_mac.lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', expected_mac):
        raise ValueError('Invalid expected ESP32 MAC')
    output = tool(port, 'read-mac')
    found = re.findall(r'MAC:\s*((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})', output)
    if not found or any(mac.lower() != expected_mac for mac in found):
        raise ValueError('Connected ESP32 identity does not match the configured board')


def wifi_provisioning_command(ssid, password):
    ssid_bytes = ssid.encode('utf-8')
    password_bytes = password.encode('utf-8')
    if (not 1 <= len(ssid_bytes) <= 32 or '\0' in ssid or '\0' in password or
            not (8 <= len(password_bytes) <= 63 or re.fullmatch(r'[0-9a-fA-F]{64}', password))):
        raise ValueError('Set both CYD Wi-Fi secrets to a valid SSID and WPA password')
    return f'CYD-WIFI {ssid_bytes.hex()} {password_bytes.hex()}\n'.encode('ascii')


def check_boot(port, native_usb=False, ota_key=None, wifi_command=None):
    import serial
    if native_usb:
        wait_for_acm(port)
    with serial.Serial(port, 115200, timeout=0.3) as connection:
        if not native_usb:
            connection.dtr = False
            connection.rts = True
            time.sleep(0.15)
            connection.rts = False
        deadline = time.monotonic() + (45 if wifi_command else 12)
        output = bytearray()
        sent_key = False
        sent_wifi = False
        while time.monotonic() < deadline:
            output.extend(connection.read(2048))
            if b'CYD OTA provisioning ready' not in output:
                continue
            if wifi_command and not sent_wifi:
                connection.write(wifi_command)
                sent_wifi = True
            wifi_saved = b'CYD Wi-Fi credentials saved' in output
            if ota_key and not sent_key and (not wifi_command or wifi_saved):
                connection.write(f'CYD-OTA {ota_key}\n'.encode('ascii'))
                sent_key = True
        text = output.decode('utf-8', errors='replace')
        marker = 'Shelf Goblin running' if native_usb else 'entry '
    if marker not in text or any(crash in text for crash in
                ('Guru Meditation', 'Brownout', 'abort() was called', 'Backtrace:')):
            raise RuntimeError('Firmware failed the serial boot check')
    if ota_key and 'CYD OTA credential saved' not in text:
        raise RuntimeError('CYD did not confirm saving the OTA credential')
    if wifi_command:
        address = re.search(r'CYD Wi-Fi connected: ([\d.]+)\r?\n', text)
        if not address:
            raise RuntimeError('CYD did not join Wi-Fi after USB provisioning')
        print(f'CYD joined Wi-Fi at {IPv4Address(address[1])}.', flush=True)


def deploy(directory, backup_root, port, expected_mac, sha, target='cyd', ota_key=None, wifi_command=None):
    board = BOARDS[target]
    native_usb = board.chip == 'esp32s3'
    manifest, flash_args = validate_artifact(directory, sha, target)

    def tool(port, *args):
        if native_usb:
            return esptool(port, *args, chip=board.chip)
        return esptool(port, *args)

    os.umask(0o077)
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # The lock also protects against an operator running two containers at once.
    import fcntl
    with (backup_root / '.flash.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_identity(tool, port, expected_mac)
        if native_usb and 'Detected flash size: 16MB' not in tool(port, 'flash-id'):
            raise ValueError('Connected ESP32-S3 does not report 16 MB of flash')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup_dir = backup_root / f'{stamp}-{sha[:12]}'
        backup_dir.mkdir(mode=0o700)
        backup = backup_dir / 'previous-flash.bin'
        print('Backing up complete device flash privately on the M920Q.', flush=True)
        tool(port, 'read-flash', '0', hex(board.flash_size), backup)
        if backup.stat().st_size != board.flash_size:
            raise RuntimeError('Incomplete backup; refusing to flash')
        backup_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
        record = dict(git_sha=sha, mac=expected_mac.lower(), backup_sha256=backup_hash,
                      artifact=manifest, status='backed-up')
        record_path = backup_dir / 'deployment.json'
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        try:
            print(f'Flashing commit {sha}; NVS is outside all write ranges.', flush=True)
            flash_options = () if native_usb else (
                '--flash-mode', 'dio', '--flash-freq', '40m', '--flash-size', '4MB',
            )
            tool(port, 'write-flash', *flash_options, *flash_args)
            tool(port, 'verify-flash', *flash_args)
            if native_usb:
                check_boot(port, native_usb=True)
            elif wifi_command:
                check_boot(port, ota_key=ota_key, wifi_command=wifi_command)
            elif ota_key:
                check_boot(port, ota_key=ota_key)
            else:
                check_boot(port)
        except Exception:
            print('Deployment failed; restoring the complete pre-flash backup.', flush=True)
            record['status'] = 'failed'
            try:
                verify_identity(tool, port, expected_mac)
                tool(port, 'write-flash', '0', backup)
                tool(port, 'verify-flash', '0', backup)
                record['status'] = 'rolled-back'
            except Exception:
                record['status'] = 'rollback-failed'
            record_path.write_text(json.dumps(record, indent=2) + '\n')
            raise
        record['status'] = 'deployed'
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        print(f'Flash verified; boot check passed. Private backup: {backup_dir}', flush=True)


def deploy_ota(directory, sha, host, ota_key, target='cyd'):
    validate_artifact(directory, sha, target)
    address = IPv4Address(host)
    if not address.is_private or address.is_loopback or address.is_link_local or address.is_unspecified:
        raise ValueError('CYD OTA requires a private LAN IPv4 address')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect((str(address), 3232))
        local_address = route.getsockname()[0]
    uploader = runpy.run_path(str(directory / 'espota.py'))
    result = uploader['main'](['-i', str(address), '-I', local_address, '-P', '3233',
                               '-t', '3', '-a', ota_key, '-f', str(directory / 'firmware.bin')])
    if result != 0:
        raise RuntimeError('CYD OTA upload failed')
    print(f'CYD accepted the firmware for commit {sha} and is expected to reboot.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=Path, default=Path('/firmware'))
    parser.add_argument('--backups', type=Path, default=Path('/backups/esp32'))
    parser.add_argument('--port', default='/dev/esp32')
    parser.add_argument('--mac')
    parser.add_argument('--ota', action='store_true')
    parser.add_argument('--provision-wifi', action='store_true')
    parser.add_argument('--sha', required=True)
    parser.add_argument('--target', choices=BOARDS, default='cyd')
    args = parser.parse_args()
    is_cyd = args.target.startswith('cyd')
    ota_key = os.environ.get('CYD_OTA_KEY') if is_cyd else None
    if is_cyd and args.target != 'cyd' and not ota_key:
        parser.error(f'{args.target} requires its dedicated OTA key')
    if (ota_key or args.ota) and not re.fullmatch(r'[0-9a-f]{64}', ota_key or ''):
        parser.error('Set CYD_OTA_KEY to 64 lowercase hexadecimal characters')
    if args.ota:
        if args.provision_wifi:
            parser.error('Wi-Fi provisioning requires USB')
        if not is_cyd or not os.environ.get('CYD_OTA_HOST'):
            parser.error('OTA requires a CYD target and CYD_OTA_HOST')
        deploy_ota(args.artifact, args.sha, os.environ['CYD_OTA_HOST'], ota_key, args.target)
    else:
        if not args.mac:
            parser.error('USB deployment requires --mac')
        wifi_command = None
        if args.provision_wifi:
            if args.target not in ('cyd-ant', 'cyd-cat'):
                parser.error('USB Wi-Fi provisioning requires Ant or Cat')
            try:
                wifi_command = wifi_provisioning_command(os.environ.get('CYD_WIFI_SSID', ''),
                                                         os.environ.get('CYD_WIFI_PASSWORD', ''))
            except ValueError as error:
                parser.error(str(error))
        deploy(args.artifact, args.backups, args.port, args.mac, args.sha, args.target, ota_key, wifi_command)
