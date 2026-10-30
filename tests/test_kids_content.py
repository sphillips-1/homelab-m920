"""Offline-content integrity and preservation checks; no real downloads."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "services/kids/prepare-content.py"
spec = importlib.util.spec_from_file_location("kids_content", SOURCE)
content = importlib.util.module_from_spec(spec)
spec.loader.exec_module(content)


class ContentTest(unittest.TestCase):
    def test_install_and_rerun_preserve_family_catalog(self):
        data = b"test offline archive"
        with tempfile.TemporaryDirectory() as folder, patch.object(content, "ROOT", Path(folder)), \
                patch.object(content, "SHA256", hashlib.sha256(data).hexdigest()), \
                patch.object(content.urllib.request, "urlopen", return_value=io.BytesIO(data)) as fetch:
            content.main()
            catalog = Path(folder) / "arcade/catalog.json"
            catalog.write_text('[{"id":"family"}]')
            content.main()
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(catalog.read_text(), '[{"id":"family"}]')

    def test_failed_checksum_never_installs_partial_archive(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(content, "ROOT", Path(folder)), \
                patch.object(content.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")):
            with self.assertRaises(SystemExit):
                content.main()
            self.assertFalse((Path(folder) / "encyclopedia" / content.NAME).exists())
            self.assertFalse(list(Path(folder).rglob("*.part")))

    def test_existing_bad_archive_is_preserved_for_inspection(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(content, "ROOT", Path(folder)), \
                patch.object(content.urllib.request, "urlopen") as fetch:
            target = Path(folder) / "encyclopedia" / content.NAME
            target.parent.mkdir()
            target.write_bytes(b"existing")
            with self.assertRaises(SystemExit):
                content.main()
            fetch.assert_not_called()
            self.assertEqual(target.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
