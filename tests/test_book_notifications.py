import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('watch', ROOT / 'services/notifications/watch.py')
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class WatchTest(unittest.TestCase):
    def test_baseline_is_silent_and_restart_retains_seen(self):
        state = watch.advance(None, {'old': {'title': 'Old'}}, 0)
        self.assertEqual(state['pending'], {})
        watch.advance(state, {'old': {'title': 'Edited'}, 'new': {'title': 'New'}}, 60)
        self.assertEqual(set(state['pending']), {'new'})
        self.assertEqual(state['pending']['new']['stable_since'], 60)
        watch.advance(state, {'old': {'title': 'Edited'}, 'new': {'title': 'New'}}, 120)
        self.assertEqual(state['pending']['new']['stable_since'], 60)

    def test_upload_changes_restart_settle_and_removal_cancels(self):
        state = watch.advance(None, {}, 0)
        watch.advance(state, {'new': {'size': 1}}, 60)
        watch.advance(state, {'new': {'size': 2}}, 120)
        self.assertEqual(state['pending']['new']['stable_since'], 120)
        watch.advance(state, {}, 180)
        self.assertEqual(state['pending'], {})

    def test_corrupt_state_fails_closed(self):
        with self.assertRaises(ValueError):
            watch.advance({}, {'old': {}}, 0)

    def test_failed_delivery_retries_and_success_survives_restart(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            state_path = Path(directory) / 'books.json'
            book = {'title': 'New', 'author': 'Author'}
            state = watch.advance(None, {}, 0)
            watch.advance(state, {'new': book}, 0)
            with patch.object(watch, 'STATE', state_path), \
                    patch.object(watch, 'snapshot', return_value={'new': book}), \
                    patch.object(watch.Path, 'touch'), patch.object(watch.time, 'sleep'):
                watch.save(state)
                with patch.object(watch, 'notify', side_effect=RuntimeError('failure')):
                    with self.assertRaises(RuntimeError):
                        watch.cycle()
                self.assertIn('new', watch.json.loads(state_path.read_text())['pending'])
                with patch.object(watch, 'notify') as send:
                    watch.cycle()
                    watch.cycle()
                    self.assertEqual(send.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
