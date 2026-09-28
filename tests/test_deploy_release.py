"""Exercise the real release script with local Git history and fake services.

Run as root inside the network-disabled disposable CI container. Only paths in
a temporary COPY of the entry point are relocated; production guards stay on.
"""

import fcntl
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/deploy-release.sh"


class DeploymentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.state = self.root / "state"
        self.lock = self.root / "lock"
        self.events = self.root / "events"
        self.installed = self.root / "installed-deploy"
        self.env = dict(os.environ, EVENTS=str(self.events))
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Deployment Test")
        scripts = self.repo / "scripts"
        scripts.mkdir()
        for name in ("deploy-services", "verify-services", "backup-authentik",
                     "backup-applications", "backup-jellyfin"):
            self.write(scripts / (name + ".sh"), f'''#!/bin/bash
set -euo pipefail
echo {name} >> "$EVENTS"
if [[ "${{FAIL_STAGE:-}}" == "{name}" ]] &&
   {{ [[ "${{FAIL_ALWAYS:-}}" == 1 ]] || [[ "$(git -C "{self.repo}" rev-parse HEAD)" == "$TARGET" ]]; }}; then
    exit 42
fi
''')
        self.write(scripts / "deploy-release.sh", "#!/bin/bash\nexit 0\n")
        for service in ("authentik", "audiobookshelf", "jellyfin"):
            self.write(self.repo / "services" / service / "compose.yml", "old\n")
        self.git("add", ".")
        self.git("commit", "-m", "previous")
        self.previous = self.git("rev-parse", "HEAD")
        for path in (self.repo / "services").glob("*/compose.yml"):
            path.write_text("new\n")
        self.git("commit", "-am", "target")
        self.target = self.git("rev-parse", "HEAD")
        self.env["TARGET"] = self.target
        origin = self.root / "origin.git"
        subprocess.run(["git", "clone", "--bare", str(self.repo), str(origin)],
                       check=True, capture_output=True)
        self.git("remote", "add", "origin", str(origin))
        self.git("checkout", "--detach", self.previous)
        self.state.mkdir()
        (self.state / "current-sha").write_text(self.previous + "\n")
        self.write(self.root / "bin/docker", '''#!/bin/bash
set -euo pipefail
echo "docker $*" >> "$EVENTS"
if [[ "${FAIL_STAGE:-}" == config && "$*" == *"config --quiet"* ]]; then
    exit 43
fi
''')
        self.env["PATH"] = str(self.root / "bin") + os.pathsep + self.env["PATH"]
        source = SOURCE.read_text()
        for old, new in {
            '/opt/homelab': str(self.repo),
            '/srv/homelab/appdata/deployment': str(self.state),
            '/run/lock/homelab-deploy.lock': str(self.lock),
            '/usr/local/sbin/homelab-deploy': str(self.installed),
        }.items():
            self.assertIn(old, source)
            source = source.replace(old, new)
        self.entry = self.root / "release.sh"
        self.write(self.entry, source)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args],
                                       stderr=subprocess.PIPE, text=True).strip()

    def run_release(self, target=None, **env):
        return subprocess.run(["bash", str(self.entry), target or self.target],
                              env=dict(self.env, **env), capture_output=True,
                              text=True, timeout=20)

    def history(self):
        return self.events.read_text().splitlines() if self.events.exists() else []

    def test_success_backs_up_before_deployment_and_records_verified_commit(self):
        result = self.run_release()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = self.history()
        for backup in ("backup-authentik", "backup-applications", "backup-jellyfin"):
            self.assertLess(events.index(backup), events.index("deploy-services"))
        self.assertLess(events.index("deploy-services"), events.index("verify-services"))
        self.assertEqual((self.state / "current-sha").read_text().strip(), self.target)
        self.assertFalse((self.state / "pending-sha").exists())
        self.assertTrue(self.installed.exists())

    def test_rejects_invalid_and_missing_commits_before_service_changes(self):
        for target in ("main", "bad; command", "0" * 40):
            with self.subTest(target=target):
                self.assertNotEqual(self.run_release(target).returncode, 0)
                self.assertEqual(self.history(), [])

    def test_rejects_commit_outside_main(self):
        self.write(self.repo / "off-main", "unmerged")
        self.git("add", ".")
        self.git("commit", "-m", "off main")
        off_main = self.git("rev-parse", "HEAD")
        self.assertNotEqual(self.run_release(off_main).returncode, 0)
        self.assertEqual(self.history(), [])

    def test_rejects_staged_and_unstaged_changes(self):
        path = self.repo / "services/authentik/compose.yml"
        path.write_text("local changes")
        for staged in (False, True):
            with self.subTest(staged=staged):
                if staged:
                    self.git("add", ".")
                self.assertNotEqual(self.run_release().returncode, 0)
                self.assertEqual(path.read_text(), "local changes")
                self.assertEqual(self.history(), [])

    def test_rejects_concurrent_deployment(self):
        with self.lock.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertNotEqual(self.run_release().returncode, 0)
        self.assertEqual(self.history(), [])

    def test_failed_health_check_restores_and_verifies_previous_release(self):
        result = self.run_release(FAIL_STAGE="verify-services")
        self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.previous)
        self.assertEqual(self.history().count("verify-services"), 2)
        self.assertEqual((self.state / "current-sha").read_text().strip(), self.previous)
        self.assertTrue((self.state / "pending-sha").exists())
        self.assertFalse(self.installed.exists())

    def test_failed_rollback_does_not_claim_success(self):
        result = self.run_release(FAIL_STAGE="deploy-services", FAIL_ALWAYS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback failed", result.stderr)
        self.assertFalse((self.state / "current-sha").exists())
        self.assertTrue((self.state / "pending-sha").exists())

    def test_unhealthy_rollback_does_not_claim_success(self):
        result = self.run_release(FAIL_STAGE="verify-services", FAIL_ALWAYS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Rollback failed", result.stderr)
        self.assertFalse((self.state / "current-sha").exists())

    def test_failed_backup_stops_before_checkout(self):
        result = self.run_release(FAIL_STAGE="backup-authentik", FAIL_ALWAYS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.previous)
        self.assertNotIn("deploy-services", self.history())
        self.assertEqual((self.state / "current-sha").read_text().strip(), self.previous)

    def test_failed_compose_validation_never_deploys_target(self):
        result = self.run_release(FAIL_STAGE="config")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.previous)
        # Only the recovery deployment runs.
        self.assertEqual(self.history().count("deploy-services"), 1)

    def test_same_commit_retry_reapplies_services(self):
        self.git("checkout", "--detach", self.target)
        (self.state / "pending-sha").write_text(self.target + "\n")
        result = self.run_release()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("deploy-services", self.history())
        self.assertIn("verify-services", self.history())
        self.assertFalse((self.state / "pending-sha").exists())
        self.assertTrue(self.installed.exists())


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("Run these tests as root inside the disposable CI container.")
    unittest.main(verbosity=2)
