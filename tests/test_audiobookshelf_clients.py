"""Check additive reconciliation, idempotency, and failure handling without a server."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error


SOURCE = Path(__file__).resolve().parents[1] / "scripts/reconcile-audiobookshelf-clients.py"
spec = importlib.util.spec_from_file_location("clients", SOURCE)
clients = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clients)


class ClientsTest(unittest.TestCase):
    def test_preserves_clients_and_only_patches_sso_entry_settings(self):
        current = ["audiobookshelf://oauth", "audiobooth://oauth"]
        state = {clients.FIELD: current, "authActiveAuthMethods": ["openid"]}

        def api(method="GET", payload=None):
            if method == "PATCH":
                self.assertEqual(payload, {clients.FIELD: current + list(clients.REQUIRED_URIS),
                                           "authOpenIDAutoLaunch": True})
                state.update(payload)
            return dict(state)

        with patch.object(clients, "request_settings", side_effect=api) as request:
            clients.reconcile()
            clients.reconcile()
        self.assertEqual(sum(bool(call.args) and call.args[0] == "PATCH"
                             for call in request.call_args_list), 1)
        self.assertEqual(state["authActiveAuthMethods"], ["openid"])

    def test_existing_lissen_or_wildcard_does_not_write(self):
        for current in (list(clients.REQUIRED_URIS), ["*"]):
            with self.subTest(current=current), patch.object(
                clients, "request_settings", return_value={clients.FIELD: current,
                    "authActiveAuthMethods": ["openid"], "authOpenIDAutoLaunch": True}
            ) as request:
                clients.reconcile()
                request.assert_called_once_with()

    def test_rejects_missing_or_malformed_list_without_write(self):
        for current in (None, "lissen://oauth", [1], ["*", "audiobookshelf://oauth"]):
            with self.subTest(current=current), patch.object(
                clients, "request_settings", return_value={clients.FIELD: current}
            ) as request:
                with self.assertRaises(RuntimeError):
                    clients.reconcile()
                request.assert_called_once_with()

    def test_detects_unsaved_update(self):
        with patch.object(clients, "request_settings", return_value={clients.FIELD: [],
                "authActiveAuthMethods": ["openid"]}):
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
                clients.reconcile()

    def test_enables_auto_launch_without_changing_existing_callbacks(self):
        for callbacks in (list(clients.REQUIRED_URIS), ["*"]):
            state = {clients.FIELD: callbacks, "authActiveAuthMethods": ["openid"],
                     "authOpenIDAutoLaunch": False}

            def api(method="GET", payload=None):
                if method == "PATCH":
                    self.assertEqual(payload, {"authOpenIDAutoLaunch": True})
                    state.update(payload)
                return dict(state)

            with self.subTest(callbacks=callbacks), patch.object(clients, "request_settings", side_effect=api):
                clients.reconcile()
                clients.reconcile()
            self.assertEqual(state[clients.FIELD], callbacks)

    def test_refuses_auto_launch_when_openid_is_disabled(self):
        with patch.object(clients, "request_settings", return_value={clients.FIELD: [],
                "authActiveAuthMethods": ["local"]}) as request:
            with self.assertRaisesRegex(RuntimeError, "OpenID must already be enabled"):
                clients.reconcile()
            request.assert_called_once_with()

    def test_detects_unsaved_auto_launch(self):
        with patch.object(clients, "request_settings", return_value={
                clients.FIELD: list(clients.REQUIRED_URIS), "authActiveAuthMethods": ["openid"]}):
            with self.assertRaisesRegex(RuntimeError, "auto-launch verification failed"):
                clients.reconcile()

    def test_retries_unavailable_api(self):
        with patch.object(clients, "request_settings", side_effect=[
            urllib.error.URLError("starting"), {clients.FIELD: []}
        ]), patch.object(clients.time, "sleep") as sleep:
            self.assertEqual(clients.read_settings(), {clients.FIELD: []})
            sleep.assert_called_once_with(2)

    def test_authentication_failure_is_not_retried(self):
        with patch.object(clients, "request_settings", side_effect=urllib.error.HTTPError(
            "http://abs/api/auth-settings", 401, "Unauthorized", {}, None
        )), patch.object(clients.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
                clients.read_settings()
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
