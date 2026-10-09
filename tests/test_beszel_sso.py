"""Regression tests for native Beszel SSO, preserving state and cleaning credentials."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("beszel_sso", ROOT / "scripts/configure-beszel-sso.py")
sso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sso)
CREDS = {"clientId": "test-client", "clientSecret": "test-secret-do-not-log"}


class BeszelSSOTest(unittest.TestCase):
    def setUp(self):
        self.collection = {
            "id": "pb_users_auth", "fields": [{"name": "role"}],
            "oauth2": {"enabled": False, "providers": [], "mappedFields": {"name": "name"}},
            "passwordAuth": {"enabled": False},
            "createRule": "@request.context = 'oauth2'",
        }
        self.original = copy.deepcopy(self.collection)
        self.patches = []
        self.methods = {"password": {"enabled": False}, "oauth2": {
            "enabled": True, "providers": [{"name": "oidc"}],
        }}
        self.admins = 1

    def api(self, method, path, data=None, token=None):
        if path.endswith("auth-with-password"):
            return {"token": "temporary-token"}
        if "/records?" in path:
            return {"totalItems": self.admins}
        if path.endswith("auth-methods"):
            return self.methods
        if method == "PATCH":
            self.patches.append(copy.deepcopy(data))
            self.collection.update(copy.deepcopy(data))
        response = copy.deepcopy(self.collection)
        # Match PocketBase's real API: credentials are write-only.
        for provider in response["oauth2"]["providers"]:
            provider.pop("clientSecret", None)
        return response

    def run_configure(self):
        with patch.object(sso, "request", side_effect=self.api), patch.object(sso, "docker") as docker:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                sso.configure(CREDS)
        return docker, output.getvalue()

    def test_repeat_deployment_preserves_schema_and_patches_only_oauth(self):
        docker, output = self.run_configure()
        self.assertEqual(len(self.patches), 1)
        self.assertEqual(set(self.patches[0]), {"oauth2"})
        self.assertEqual(self.collection["fields"], self.original["fields"])
        self.assertEqual(self.collection["oauth2"]["mappedFields"], {"name": "name"})
        self.run_configure()
        self.assertEqual(len(self.patches), 2)
        self.assertEqual(self.patches[0], self.patches[1])
        self.assertEqual(self.collection["oauth2"]["providers"][0]["clientSecret"], CREDS["clientSecret"])
        self.assertEqual(docker.call_args_list[-1].args[3:5], ("superuser", "delete"))
        self.assertNotIn(CREDS["clientSecret"], output)

    def test_existing_other_providers_cannot_bypass_authentik(self):
        self.collection["oauth2"]["providers"] = [{"name": "google"}]
        self.run_configure()
        providers = self.collection["oauth2"]["providers"]
        self.assertEqual([provider["name"] for provider in providers], ["oidc"])
        self.assertTrue(providers[0]["pkce"])

    def test_api_failure_still_removes_temporary_superuser(self):
        def failing_api(method, path, data=None, token=None):
            if method == "PATCH":
                raise RuntimeError("Simulated API failure")
            return self.api(method, path, data, token)
        with patch.object(sso, "request", side_effect=failing_api), patch.object(sso, "docker") as docker:
            with self.assertRaisesRegex(RuntimeError, "Simulated API failure"):
                sso.configure(CREDS)
        self.assertEqual(docker.call_args_list[-1].args[3:5], ("superuser", "delete"))

    def test_cli_creation_failure_still_attempts_cleanup(self):
        with patch.object(sso, "docker", side_effect=[RuntimeError("CLI failed"), ""]) as docker:
            with self.assertRaisesRegex(RuntimeError, "CLI failed"):
                sso.configure(CREDS)
        self.assertEqual(docker.call_count, 2)
        self.assertEqual(docker.call_args.args[3:5], ("superuser", "delete"))

    def test_missing_first_administrator_refuses_to_modify_users(self):
        self.admins = 0
        with patch.object(sso, "request", side_effect=self.api), patch.object(sso, "docker") as docker:
            with self.assertRaisesRegex(RuntimeError, "first Beszel administrator"):
                sso.configure(CREDS)
        self.assertEqual(self.patches, [])
        self.assertEqual(docker.call_args.args[3:5], ("superuser", "delete"))

    def test_password_or_extra_provider_fails_verification(self):
        for methods in (
            {**self.methods, "password": {"enabled": True}},
            {"password": {"enabled": False}, "oauth2": {"enabled": True,
             "providers": [{"name": "oidc"}, {"name": "google"}]}},
        ):
            with self.subTest(methods=methods), patch.object(sso, "request", return_value=methods):
                with self.assertRaises(RuntimeError):
                    sso.verify_auth_methods()

    def test_readback_mismatch_fails_deployment(self):
        def failing_api(method, path, data=None, token=None):
            if method == "PATCH":
                return {}  # Server claims success but discards settings.
            return self.api(method, path, data, token)
        with patch.object(sso, "request", side_effect=failing_api), patch.object(sso, "docker") as docker:
            with self.assertRaisesRegex(RuntimeError, "did not persist"):
                sso.configure(CREDS)
        self.assertEqual(docker.call_args.args[3:5], ("superuser", "delete"))

    def test_credentials_captured_without_logging(self):
        payload = sso.MARKER + json.dumps(CREDS)
        with patch.object(sso, "docker", return_value="shell banner\n" + payload + "\n"):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(sso.get_credentials(), CREDS)
        self.assertEqual(output.getvalue(), "")
        for value in (payload + "\n" + payload, sso.MARKER + "{}", sso.MARKER + "invalid", ""):
            with self.subTest(value=value), patch.object(sso, "docker", return_value=value):
                with self.assertRaises(RuntimeError):
                    sso.get_credentials()

    def test_docker_failure_does_not_disclose_secret(self):
        result = type("Result", (), {"returncode": 1, "stdout": CREDS["clientSecret"],
                                     "stderr": CREDS["clientSecret"]})()
        with patch.object(sso.subprocess, "run", return_value=result):
            with self.assertRaises(RuntimeError) as caught:
                sso.docker("exec", "beszel", "secret-argument")
        self.assertNotIn(CREDS["clientSecret"], str(caught.exception))
        self.assertNotIn("secret-argument", str(caught.exception))

    def test_real_http_error_body_cannot_disclose_credentials(self):
        class Handler(BaseHTTPRequestHandler):
            def do_PATCH(self):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(CREDS["clientSecret"].encode())
            def log_message(self, *args):
                pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(sso, "BASE_URL", f"http://127.0.0.1:{server.server_port}"):
                with self.assertRaisesRegex(RuntimeError, "HTTP 400") as caught:
                    sso.request("PATCH", "/api/collections/users", CREDS)
            self.assertNotIn(CREDS["clientSecret"], str(caught.exception))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class AuthentikProviderTest(unittest.TestCase):
    def test_repeated_reconciliation_retains_credentials_and_both_access_checks(self):
        # Execute the checked-in reconciler against an in-memory ORM adapter.
        # This catches drift in provider defaults, scopes, and binding targets.
        import types
        from unittest.mock import Mock

        class Row(types.SimpleNamespace):
            def save(self):
                pass

        class Manager:
            def __init__(self, rows=()):
                self.rows = list(rows)

            def get(self, **query):
                found = [r for r in self.rows if all(getattr(r, k, None) == v for k, v in query.items())]
                if len(found) != 1:
                    raise RuntimeError("Missing or ambiguous ORM fixture")
                return found[0]

            def update_or_create(self, defaults, **query):
                found = [r for r in self.rows if all(getattr(r, k, None) == v for k, v in query.items())]
                created = not found
                if created:
                    row = Row(client_id="retained-id", client_secret="retained-secret",
                              property_mappings=Mock(), **query)
                    self.rows.append(row)
                else:
                    row = found[0]
                for key, value in defaults.items():
                    setattr(row, key, value)
                return row, created

        template = Row(name="Audiobookshelf OIDC", authentication_flow="login",
                       authorization_flow="consent", invalidation_flow="logout", signing_key="key")
        group = Row(name="status-users")
        scopes = [Row(managed=f"goauthentik.io/providers/oauth2/scope-{scope}")
                  for scope in ("openid", "profile")]
        models = {
            "Application": Manager(), "Group": Manager([group]), "PolicyBinding": Manager(),
            "ExpressionPolicy": Manager(), "OAuth2Provider": Manager([template]),
            "ScopeMapping": Manager(scopes),
        }
        modules = {}
        for path, names in {
            "django.db": ["transaction"],
            "authentik.core.models": ["Application", "Group"],
            "authentik.policies.models": ["PolicyBinding"],
            "authentik.policies.expression.models": ["ExpressionPolicy"],
            "authentik.providers.oauth2.models": ["OAuth2Provider", "ScopeMapping", "RedirectURI"],
        }.items():
            module = types.ModuleType(path)
            for name in names:
                if name == "transaction":
                    value = types.SimpleNamespace(atomic=contextlib.nullcontext)
                elif name == "RedirectURI":
                    value = Row
                else:
                    value = types.SimpleNamespace(objects=models[name])
                setattr(module, name, value)
            modules[path] = module
        code = (ROOT / "scripts/reconcile-beszel-sso.py").read_text(encoding="utf-8")
        with patch.dict("sys.modules", modules):
            for _ in range(2):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    exec(compile(code, "reconcile-beszel-sso.py", "exec"), {})
                credentials = json.loads(output.getvalue().strip().removeprefix(sso.MARKER))
                self.assertEqual(credentials, {"clientId": "retained-id", "clientSecret": "retained-secret"})
        provider = models["OAuth2Provider"].get(name="Beszel OIDC")
        self.assertEqual(len(models["OAuth2Provider"].rows), 2)
        self.assertEqual(provider.grant_types, ["authorization_code"])
        self.assertEqual(provider.client_type, "confidential")
        self.assertEqual(provider.redirect_uris[0].matching_mode, "strict")
        self.assertEqual(provider.redirect_uris[0].url, "https://status.shelfgoblin.dev/api/oauth2-redirect")
        app = models["Application"].get(slug="beszel")
        self.assertTrue(app.meta_hide)
        self.assertEqual(app.policy_engine_mode, "all")
        bindings = models["PolicyBinding"].rows
        self.assertEqual(len(bindings), 2)
        self.assertIs(bindings[0].group, group)
        self.assertIn('sources.filter(slug="google")', bindings[1].policy.expression)
        self.assertTrue(all(b.enabled and not b.negate and not b.failure_result for b in bindings))
        mapped = provider.property_mappings.set.call_args.args[0]
        self.assertEqual(len(mapped), 3)
        self.assertEqual(mapped[-1].scope_name, "email")
        self.assertIn('"email_verified"', mapped[-1].expression)


if __name__ == "__main__":
    unittest.main(verbosity=2)
