"""Render actual tunnel templates and test routes with cloudflared itself."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CloudflareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model = json.loads(subprocess.check_output(
            ["docker", "compose", "-f", str(ROOT / "services/cloudflared/compose.yml"),
             "config", "--format", "json"], text=True))
        cls.image = model["services"]["cloudflared"]["image"]
        subprocess.run(["docker", "pull", cls.image], check=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "config/cloudflared", self.root / "config/cloudflared")
        service = self.root / "services/cloudflared"
        service.mkdir(parents=True)
        credentials = self.root / "dummy.json"
        credentials.write_text("{}")
        (service / ".env").write_text(
            "CLOUDFLARE_DOMAIN=example.invalid\n"
            "CLOUDFLARE_TUNNEL_ID=01234567-89ab-cdef-0123-456789abcdef\n"
            f"CLOUDFLARE_TUNNEL_CREDENTIALS_FILE={credentials}\n")
        self.runtime = self.root / "runtime"
        script = (ROOT / "scripts/configure-cloudflared.sh").read_text()
        script = script.replace('/opt/homelab', str(self.root))
        script = script.replace('/srv/homelab/appdata/cloudflared', str(self.runtime))
        self.script = self.root / "render.sh"
        self.script.write_text(script)

    def cloudflared(self, *args):
        return subprocess.check_output(
            ["docker", "run", "--rm", "--network", "none", "--user", "0:0",
             "-v", f"{self.runtime}:/etc/cloudflared:ro", self.image,
             "tunnel", "--config", "/etc/cloudflared/config.yml", "ingress", *args],
            text=True, stderr=subprocess.STDOUT)

    def test_rendered_modes_and_routes(self):
        for mode in ("safe", "sso", "test", "access"):
            with self.subTest(mode=mode):
                subprocess.run(["bash", str(self.script), "--mode", mode], check=True,
                               capture_output=True)
                self.assertNotIn("__", (self.runtime / "config.yml").read_text())
                self.cloudflared("validate")
                routes = {
                    "auth.example.invalid/invite/01234567-89ab-cdef-0123-456789abcdef": "http://invitation-provisioner:8080",
                    "auth.example.invalid/if/flow/default-authentication-flow/": "http://authentik-server:9000",
                    "jellyfin.example.invalid/": "http_status:404",
                    "unknown.example.invalid/": "http_status:404",
                    "torrents.example.invalid/": "http://m920-qbittorrent:8091" if mode == "sso" else "http_status:404",
                    "books.example.invalid/": "http_status:404" if mode == "safe" else
                        "http://authentik-server:9000" if mode == "sso" else "http://calibre-web:8083",
                    "status.example.invalid/": "http_status:404" if mode == "safe" else
                        "http://authentik-server:9000" if mode == "sso" else "http://beszel:8090",
                    "audiobooks.example.invalid/": "http_status:404" if mode == "safe" else "http://audiobookshelf-gateway:80",
                }
                for url, service in routes.items():
                    with self.subTest(url=url):
                        self.assertIn("service: " + service, self.cloudflared("rule", "https://" + url))


if __name__ == "__main__":
    unittest.main(verbosity=2)
