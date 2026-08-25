#!/usr/bin/env python3

import os
import unittest


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


if __name__ == "__main__":
    unittest.main()
