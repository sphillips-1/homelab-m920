import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('notify_release', Path(__file__).with_name('notify-release.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseNotificationTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            'DISCORD_WEBHOOK': 'https://discord.com/api/webhooks/123/test_token',
            'GITHUB_SERVER_URL': 'https://github.com',
            'GITHUB_REPOSITORY': 'example/library',
            'GITHUB_RUN_NUMBER': '42', 'GITHUB_RUN_ID': '1234',
        }

    def test_confirmed_delivery_includes_matching_apk_and_disables_mentions(self):
        response = io.BytesIO(b'{"id":"5678"}')
        response.status = 200
        send = Mock(return_value=response)
        module.notify(self.env, send)
        request = send.call_args.args[0]
        self.assertTrue(request.full_url.endswith('?wait=true'))
        self.assertEqual(request.method, 'POST')
        payload = json.loads(request.data)
        self.assertIn('/releases/download/shelfgoblin-build-42/ShelfGoblin.apk', payload['content'])
        self.assertIn('/releases/tag/shelfgoblin-build-42', payload['content'])
        self.assertEqual(payload['allowed_mentions'], {'parse': []})
        self.assertEqual(send.call_args.kwargs['timeout'], 30)

    def test_missing_or_invalid_secret_never_sends(self):
        for value in ['', 'https://example.com/api/webhooks/123/token']:
            send = Mock()
            with self.assertRaises(ValueError):
                module.notify(dict(self.env, DISCORD_WEBHOOK=value), send)
            send.assert_not_called()

    def test_unconfirmed_delivery_fails(self):
        response = io.BytesIO(b'{}')
        response.status = 200
        with self.assertRaises(ValueError):
            module.notify(self.env, Mock(return_value=response))

    def test_timeout_is_not_retried(self):
        send = Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):
            module.notify(self.env, send)
        send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
