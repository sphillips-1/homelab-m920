#!/usr/bin/env python3
"""Package only flashable binaries and their checksums, never device state."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


from esp32_profiles import BOARDS

PARTS = BOARDS['cyd'].parts


def package(build, boot_app, output, sha, target='cyd'):
    board = BOARDS[target]
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Expected a full lowercase Git commit SHA')
    output.mkdir(parents=True, exist_ok=True)
    images = []
    for name, offset, limit in board.parts:
        source = boot_app if name == 'boot_app0.bin' else build / name
        data = source.read_bytes()
        if not 0 < len(data) <= limit:
            raise ValueError(f'Invalid size for {name}')
        shutil.copyfile(source, output / name)
        images.append(dict(file=name, offset=offset, size=len(data),
                           sha256=hashlib.sha256(data).hexdigest()))
    manifest = dict(schema=1, git_sha=sha, chip=board.chip, flash_size=board.flash_size, images=images)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--boot-app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sha', required=True)
    parser.add_argument('--target', choices=BOARDS, default='cyd')
    args = parser.parse_args()
    package(args.build, args.boot_app, args.output, args.sha, args.target)
