"""Exercise boot recovery order and failure handling without touching services."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RecoveryTest(unittest.TestCase):
    def run_recovery(self, fail):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            events = root / 'events'
            for name, stage in [('check-m920-torrent-storage.sh', 'storage'),
                                ('verify-torrent-connectivity.sh', 'verify')]:
                (root / 'scripts' / name).write_text(
                    f'echo {stage} >> "$EVENTS"\n[[ "$FAIL" != {stage} ]]\n')
            docker = root / 'docker'
            docker.write_text('''#!/bin/bash
echo "$*" >> "$EVENTS"
if [[ "$*" == *"--no-deps"* ]]; then
    [[ "$FAIL" != sidecars ]]
else
    [[ "$FAIL" != app ]]
fi
''')
            docker.chmod(0o755)
            script = root / 'recover.sh'
            script.write_text((ROOT / 'scripts/recover-torrent-stack.sh').read_text()
                              .replace('/opt/homelab', str(root)))
            result = subprocess.run(['bash', str(script)], capture_output=True,
                                    env=dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'],
                                             EVENTS=str(events), FAIL=fail), timeout=10)
            return result.returncode, events.read_text().splitlines()

    def test_order(self):
        code, events = self.run_recovery('none')
        self.assertEqual(code, 0)
        self.assertEqual(events[0], 'storage')
        self.assertIn('--wait --wait-timeout 180 qbittorrent', events[1])
        self.assertIn('--no-deps --force-recreate', events[2])
        self.assertEqual(events[3], 'verify')

    def test_failure_stops_later_stages(self):
        for stage, count in [('storage', 1), ('app', 2), ('sidecars', 3), ('verify', 4)]:
            with self.subTest(stage=stage):
                code, events = self.run_recovery(stage)
                self.assertNotEqual(code, 0)
                self.assertEqual(len(events), count)


if __name__ == '__main__':
    unittest.main()
