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
    def test_preserves_clients_and_only_patches_redirects(self):
        current = ["audiobookshelf://oauth", "audiobooth://oauth"]
        state = {clients.FIELD: current, "authActiveAuthMethods": ["openid"]}

        def api(method="GET", payload=None):
            if method == "PATCH":
                self.assertEqual(payload, {clients.FIELD: current + ["lissen://oauth"]})
                state.update(payload)
            return dict(state)

        with patch.object(clients, "request_settings", side_effect=api) as request:
            clients.reconcile()
            clients.reconcile()
        self.assertEqual(sum(call.args == ("PATCH", {clients.FIELD: state[clients.FIELD]})
                             for call in request.call_args_list), 1)
        self.assertEqual(state["authActiveAuthMethods"], ["openid"])

    def test_existing_lissen_or_wildcard_does_not_write(self):
        for current in (["lissen://oauth"], ["*"]):
            with self.subTest(current=current), patch.object(
                clients, "request_settings", return_value={clients.FIELD: current}
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
        with patch.object(clients, "request_settings", return_value={clients.FIELD: []}):
            with self.assertRaisesRegex(RuntimeError, "verification failed"):
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
