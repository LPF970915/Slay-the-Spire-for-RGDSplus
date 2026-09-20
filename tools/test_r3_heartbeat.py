"""A focus heartbeat must not depend on removable-card timestamp precision."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype/p1"))
sys.path.insert(0, str(ROOT / "prototype/r3"))
from touch_bridge import heartbeat_focused


class HeartbeatTests(unittest.TestCase):
    def test_recent_focused(self):
        self.assertTrue(heartbeat_focused("1 100.250000\n", 100.5))

    def test_lost_focus(self):
        self.assertFalse(heartbeat_focused("0 100.250000\n", 100.5))

    def test_stale_and_future(self):
        for timestamp in ("98.5", "101", "nan", "inf", "-inf"):
            self.assertFalse(heartbeat_focused("1 " + timestamp, 100))

    def test_partial_unknown_and_legacy(self):
        for text in ("", "1", "1 bad", "2 100", "1 100 extra"):
            self.assertFalse(heartbeat_focused(text, 100))


if __name__ == "__main__":
    unittest.main()
