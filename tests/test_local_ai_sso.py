"""Verify signing-key continuity without Docker or live credentials."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/configure-local-ai-sso.py"
spec = importlib.util.spec_from_file_location("local_ai_sso", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SessionKeyTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.key = self.directory / "open-webui/.webui_secret_key"

    def test_running_key_survives_first_migration_and_rerun(self):
        results = [SimpleNamespace(returncode=0, stdout="existing-private-test-key\n"),
                   SimpleNamespace(returncode=0, stdout="true\n")]
        with patch.object(module.subprocess, "run", side_effect=results):
            module.preserve_session_key(self.directory)
        self.assertEqual(self.key.read_text().strip(), "existing-private-test-key")
        with patch.object(module.subprocess, "run", side_effect=AssertionError("Unexpected Docker probe")):
            module.preserve_session_key(self.directory)
        self.assertEqual(self.key.read_text().strip(), "existing-private-test-key")

    def test_running_service_key_is_never_silently_rotated(self):
        results = [SimpleNamespace(returncode=1, stdout=""),
                   SimpleNamespace(returncode=0, stdout="true\n")]
        with patch.object(module.subprocess, "run", side_effect=results):
            with self.assertRaises(SystemExit):
                module.preserve_session_key(self.directory)
        self.assertFalse(self.key.exists())

    def test_first_install_generates_key(self):
        results = [SimpleNamespace(returncode=1, stdout=""),
                   SimpleNamespace(returncode=1, stdout="")]
        with patch.object(module.subprocess, "run", side_effect=results):
            module.preserve_session_key(self.directory)
        self.assertGreaterEqual(len(self.key.read_text().strip()), 48)

    def test_empty_persistent_key_is_rejected(self):
        self.key.parent.mkdir()
        self.key.write_text("")
        with self.assertRaises(SystemExit):
            module.preserve_session_key(self.directory)


if __name__ == "__main__":
    unittest.main(verbosity=2)
