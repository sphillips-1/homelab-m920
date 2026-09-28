#!/usr/bin/env python3

import os
import io
import json
import unittest
from unittest.mock import patch, Mock
import urllib.error


os.environ.setdefault("AUDIOBOOKSHELF_API_TOKEN", "test")
os.environ.setdefault("AUTHENTIK_INVITATION_PROVISIONER_TOKEN", "test")

import server


class RouteMatchingTest(unittest.TestCase):
    def test_invite_creator_accepts_both_trailing_slash_forms(self):
        for target in ("/invite/new", "/invite/new/"):
            self.assertIn(server.request_path(target), server.INVITE_CREATOR_PATHS)

    def test_invite_creator_ignores_query_string(self):
        self.assertIn(
            server.request_path("/invite/new/?next=%2F"),
            server.INVITE_CREATOR_PATHS,
        )

    def test_invitation_uuid_ignores_query_string(self):
        token = "01234567-89ab-cdef-0123-456789abcdef"
        self.assertIsNotNone(
            server.INVITE_PATH.fullmatch(server.request_path(f"/invite/{token}?x=1"))
        )


class ProvisioningFailureTest(unittest.TestCase):
    def request(self, payload, token="Bearer test"):
        handler = server.Handler.__new__(server.Handler)
        handler.path = "/provision"
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        handler.headers = {"Content-Length": str(len(raw)), "Authorization": token}
        handler.rfile = io.BytesIO(raw)
        handler.respond = Mock()
        with patch.object(server, "PROVISIONER_TOKEN", "test"):
            handler.do_POST()
        return handler.respond.call_args.args

    def test_missing_or_wrong_auth_never_provisions(self):
        with patch.object(server, "provision") as provision:
            for token in ("", "Bearer wrong"):
                self.assertEqual(self.request({}, token)[0], 401)
            provision.assert_not_called()

    def test_malformed_payloads_never_provision(self):
        with patch.object(server, "provision") as provision:
            for payload in (b"{", [], None, {"email": []}, {"email": "no-address"},
                            {"email": "a@b", "name": []},
                            {"email": "a@b", "services": "audiobookshelf"},
                            {"email": "a@b", "services": [[]]}):
                with self.subTest(payload=payload):
                    self.assertIn(self.request(payload)[0], (400, 409))
            provision.assert_not_called()

    def test_unsupported_services_make_no_upstream_calls(self):
        with patch.object(server, "abs_request") as upstream:
            for services in ([], ["unknown"], ["audiobookshelf", "unknown"]):
                self.assertEqual(self.request({"email": "a@b", "services": services})[0], 409)
            upstream.assert_not_called()

    def test_upstream_errors_return_failure(self):
        for error in (urllib.error.URLError("offline"), TimeoutError("timeout"),
                      urllib.error.HTTPError("http://example.invalid", 503, "unavailable", {}, None)):
            with self.subTest(error=error), patch.object(server, "abs_request", side_effect=error):
                self.assertEqual(self.request({"email": "a@b", "services": ["audiobookshelf"]})[0], 502)

    def test_duplicate_requests_reuse_existing_account(self):
        account = {"id": "reader", "email": "reader@example.invalid", "isActive": True}
        with patch.object(server, "abs_request", side_effect=[
            {"users": []}, {}, {"users": [account]}, {"users": [account]},
        ]) as upstream:
            first = server.provision_audiobookshelf(" Reader@Example.invalid ", "Reader")
            second = server.provision_audiobookshelf("reader@example.invalid", "Reader")
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["user_id"], second["user_id"])
            self.assertEqual(sum(c.args[0] == "POST" for c in upstream.call_args_list), 1)

    def test_ambiguous_or_inactive_accounts_are_not_modified(self):
        for users in ([{"email": "a@b", "id": "1"}, {"email": "a@b", "id": "2"}],
                      [{"email": "a@b", "id": "1", "isActive": False}]):
            with patch.object(server, "abs_request", return_value={"users": users}) as upstream:
                with self.assertRaises(ValueError):
                    server.provision_audiobookshelf("a@b", "Reader")
                upstream.assert_called_once_with("GET", "/api/users")

    def test_malformed_invitation_path_does_not_set_cookie(self):
        handler = server.Handler.__new__(server.Handler)
        handler.path = "/invite/not-a-uuid"
        handler.respond = Mock()
        handler.send_header = Mock()
        handler.do_GET()
        self.assertEqual(handler.respond.call_args.args[0], 404)
        handler.send_header.assert_not_called()


if __name__ == "__main__":
    unittest.main()
