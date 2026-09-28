"""Check fully resolved, tracked Compose models against homelab boundaries."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Existing private-access host ports. Any new publication requires review here.
PORTS = {"audiobookshelf-gateway": (13378, 80), "authentik-server": (9000, 9000),
         "calibre-web": (8083, 8083), "jellyfin": (8096, 8096), "beszel": (8090, 8090)}


class ComposePolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = subprocess.check_output(
            ["git", "ls-files", "services/*/compose.yml"], cwd=ROOT, text=True).splitlines()
        cls.models = {}
        for file in files:
            cls.models[file] = json.loads(subprocess.check_output(
                ["docker", "compose", "-f", file, "--profile", "*", "config", "--format", "json"],
                cwd=ROOT, text=True))

    def test_storage_and_network_boundaries(self):
        for file, model in self.models.items():
            for service in model["services"].values():
                name = service["container_name"]
                with self.subTest(service=name):
                    self.assertFalse(service.get("privileged", False))
                    self.assertNotIn(service.get("pid"), ("host",))
                    if service.get("network_mode") == "host":
                        self.assertEqual(name, "beszel-agent")
                    expected = [PORTS[name]] if name in PORTS else []
                    actual = [(int(p["published"]), int(p["target"])) for p in service.get("ports", [])]
                    self.assertEqual(actual, expected)
                    for port in service.get("ports", []):
                        self.assertEqual(port.get("protocol", "tcp"), "tcp")
                        if name == "jellyfin":
                            self.assertNotIn(port.get("host_ip", ""), ("", "0.0.0.0", "::"))
                    for volume in service.get("volumes", []):
                        self.assertEqual(volume["type"], "bind", "Persistent volumes must have explicit host paths")
                        source = Path(volume["source"])
                        if source == Path("/var/run/docker.sock"):
                            self.assertEqual(name, "beszel-agent")
                            self.assertTrue(volume.get("read_only"))
                        elif source.is_relative_to(ROOT):
                            self.assertTrue(volume.get("read_only"), "Repository mounts must be read-only")
                            self.assertTrue(source.exists(), f"Missing repository mount: {source}")
                        else:
                            self.assertTrue(source.is_relative_to("/srv/homelab"), str(source))
                        if name == "jellyfin" and volume["target"].startswith("/media/"):
                            self.assertTrue(volume.get("read_only"), "Jellyfin media must remain read-only")

    def test_monitoring_agent_profile(self):
        model = self.models["services/monitoring/compose.yml"]
        agent = model["services"]["beszel-agent"]
        self.assertEqual(agent["profiles"], ["agent"])
        self.assertEqual(agent["environment"]["LISTEN"], "/beszel_socket/beszel.sock")
        self.assertEqual(agent["depends_on"]["beszel"]["condition"], "service_healthy")
        mounts = {v["target"]: v["source"] for v in agent["volumes"]}
        hub_mounts = {v["target"]: v["source"] for v in model["services"]["beszel"]["volumes"]}
        self.assertEqual(mounts["/beszel_socket"], hub_mounts["/beszel_socket"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
