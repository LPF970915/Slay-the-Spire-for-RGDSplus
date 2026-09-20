"""Long-press and process-scope tests without game resources."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rgds_exit", ROOT / "platform/rgds_exit.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class ExitTests(unittest.TestCase):
    def test_tap_repeat_hold_release(self):
        hold = guard.Hold()
        hold.event(5, 310, 1, 10)
        hold.event(5, 310, 2, 11)
        hold.event(5, 310, 1, 11.1)
        self.assertFalse(hold.expired(11.49))
        self.assertTrue(hold.expired(11.5))
        hold.event(5, 310, 0, 11.6)
        self.assertFalse(hold.expired(20))

    def test_short_presses_do_not_accumulate(self):
        hold = guard.Hold()
        for now in (1, 3, 5):
            hold.event(5, 310, 1, now)
            self.assertFalse(hold.expired(now + 0.2))
            hold.event(5, 310, 0, now + 0.3)
        self.assertFalse(hold.expired(100))

    def test_removed_device_and_independent_keys(self):
        hold = guard.Hold()
        hold.event(5, 310, 1, 1)
        hold.event(4, 158, 1, 2)
        hold.cancel(5)
        self.assertFalse(hold.expired(3))
        self.assertTrue(hold.expired(3.5))
        hold.cancel(4)
        self.assertFalse(hold.expired(100))

    def test_pid_reuse_never_signalled(self):
        with patch.object(guard, "identity", return_value="new"), \
             patch.object(guard.os, "kill") as kill:
            guard.terminate((123, "old"), grace=0)
            kill.assert_not_called()

    def test_hung_game_gets_term_then_kill(self):
        with patch.object(guard, "identity", return_value="birth"), \
             patch.object(guard.signal, "SIGKILL", 9, create=True), \
             patch.object(guard.os, "kill") as kill:
            guard.terminate((123, "birth"), grace=0)
            self.assertEqual([c.args[1] for c in kill.call_args_list],
                             [guard.signal.SIGTERM, guard.signal.SIGKILL])

    def test_clean_exit_needs_no_kill(self):
        with patch.object(guard, "identity", side_effect=["birth", None, None]), \
             patch.object(guard.os, "kill") as kill:
            guard.terminate((123, "birth"), grace=0)
            kill.assert_called_once_with(123, guard.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
