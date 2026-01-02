import unittest
from unittest.mock import MagicMock, patch

from bench_finder.core.streetview import StreetViewClient


class TestBackoff(unittest.TestCase):
    def setUp(self):
        # Mock config values to speed up tests
        self.initial_wait = 1.0
        self.decrease_step = 0.2

        # Patch the config values in the module where they are used
        patcher1 = patch(
            "bench_finder.core.streetview.BACKOFF_INITIAL_WAIT", self.initial_wait
        )
        patcher2 = patch(
            "bench_finder.core.streetview.BACKOFF_DECREASE_STEP", self.decrease_step
        )
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)
        patcher1.start()
        patcher2.start()

        # Mock time.sleep to avoid actual waiting but verify calls
        self.sleep_mock = MagicMock()
        patcher3 = patch("time.sleep", self.sleep_mock)
        self.addCleanup(patcher3.stop)
        patcher3.start()

    def test_backoff_logic(self):
        client = StreetViewClient()

        # 1. Trigger backoff
        print("Testing trigger_backoff...")
        client._trigger_backoff()

        # Verify initial wait
        self.sleep_mock.assert_called_with(self.initial_wait)
        # Verify state update
        expected_next_backoff = max(0, self.initial_wait - self.decrease_step)
        self.assertAlmostEqual(client.current_backoff, expected_next_backoff)
        print(f"Verified initial wait: {self.initial_wait}s")

        # 2. Handle backoff (next call)
        print("Testing handle_backoff (1st time)...")
        self.sleep_mock.reset_mock()
        client._handle_backoff()

        # Verify wait
        self.sleep_mock.assert_called_with(expected_next_backoff)
        # Verify state update
        expected_next_backoff_2 = max(0, expected_next_backoff - self.decrease_step)
        self.assertAlmostEqual(client.current_backoff, expected_next_backoff_2)
        print(f"Verified decreasing wait: {expected_next_backoff}s")

        # 3. Handle backoff until cleared
        print("Testing handle_backoff until cleared...")
        while client.current_backoff > 0:
            prev_backoff = client.current_backoff
            self.sleep_mock.reset_mock()
            client._handle_backoff()
            self.sleep_mock.assert_called_with(prev_backoff)
            print(f"Verified wait: {prev_backoff}s")

        # Verify cleared
        self.assertEqual(client.current_backoff, 0)

        # 4. Handle backoff when cleared (should do nothing)
        self.sleep_mock.reset_mock()
        client._handle_backoff()
        self.sleep_mock.assert_not_called()
        print("Verified no wait when backoff cleared")


if __name__ == "__main__":
    unittest.main()
