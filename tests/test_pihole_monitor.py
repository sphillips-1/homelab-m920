import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).resolve().parents[1] / 'services/pihole-monitor/monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class TransitionTests(unittest.TestCase):
    def test_threshold_no_duplicates_and_recovery(self):
        state, messages = {}, []
        for _ in range(2):
            monitor.step(state, False, messages.append)
        self.assertEqual(messages, [])
        monitor.step(state, False, messages.append)
        restored = dict(state)  # State retained across restart.
        monitor.step(restored, False, messages.append)
        self.assertEqual(len(messages), 1)
        monitor.step(restored, True, messages.append)
        monitor.step(restored, True, messages.append)
        self.assertEqual(len(messages), 2)
        self.assertFalse(restored['outage_notified'])

    def test_failed_delivery_retried(self):
        state = {'failures': 2}
        def fail(_):
            raise OSError('unavailable')
        with self.assertRaises(OSError):
            monitor.step(state, False, fail)
        self.assertFalse(state.get('outage_notified', False))
        messages = []
        monitor.step(state, False, messages.append)
        with self.assertRaises(OSError):
            monitor.step(state, True, fail)
        self.assertTrue(state['outage_notified'])
        monitor.step(state, True, messages.append)
        self.assertEqual(len(messages), 2)

    def test_brief_failure_and_initial_success_silent(self):
        state, messages = {}, []
        for result in [True, False, False, True]:
            monitor.step(state, result, messages.append)
        self.assertEqual(messages, [])


if __name__ == '__main__':
    unittest.main()
