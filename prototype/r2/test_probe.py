import unittest

from probe import POINTS, Probe


class ProbeTests(unittest.TestCase):
    def tap(self, p, uid, x, y):
        p.displayed()
        p.down(uid, x, y)
        p.up(uid)

    def test_grid_three_rounds(self):
        p = Probe(source="model-replay")
        for index in range(27):
            x, y = p.expected
            self.tap(p, index, x + 3, y + 4)
        report = p.report()
        self.assertTrue(report["measured_pass"])
        self.assertFalse(report["physical_verified"])
        self.assertEqual(report["max_error_px"], 5)

    def test_large_error_kept_not_calibrated_away(self):
        p = Probe()
        self.tap(p, 1, 28, 16)
        self.assertEqual(p.samples[0]["dx"], 12)
        self.assertEqual(p.samples[0]["measured"], [28, 16])
        self.assertEqual(p.report()["within_8px"], 0)

    def test_wrong_point_does_not_advance(self):
        p = Probe()
        self.tap(p, 1, 512, 384)
        self.assertEqual(p.expected, POINTS[0])
        self.assertEqual(p.misses, 1)

    def test_no_duplicate_up(self):
        p = Probe()
        self.tap(p, 7, 16, 16)
        p.up(7)
        self.assertEqual(len(p.samples), 1)

    def test_new_target_must_be_displayed(self):
        p = Probe()
        self.tap(p, 1, 16, 16)
        p.down(2, 512, 16)
        p.up(2)
        self.assertEqual(len(p.samples), 1)

    def test_stale_release_does_not_clear_new_contact(self):
        p = Probe()
        p.displayed()
        p.down(1, 16, 16)
        p.cancel("focus")
        p.down(2, 16, 16)
        p.up(1)
        self.assertEqual(p.owner, 2)

    def test_movement_during_grid_tap_is_rejected(self):
        p = Probe()
        p.displayed()
        p.down(1, 16, 16)
        p.move(1, 40, 16)
        p.up(1)
        self.assertEqual(len(p.samples), 0)
        self.assertEqual(p.status, "moving-tap")

    def test_drag_records_once(self):
        p = Probe()
        p.button("r")
        p.down(1, 0, 0)
        p.move(1, 1024, 768)
        p.up(1)
        p.up(1)
        self.assertEqual(p.drags, 1)
        self.assertEqual(p.distance, 1280)

    def test_cancel_preserves_samples(self):
        p = Probe()
        self.tap(p, 1, 16, 16)
        p.button("b")
        self.assertEqual(len(p.samples), 1)

    def test_reset_archives_run(self):
        events = []
        p = Probe(events.append)
        self.tap(p, 1, 16, 16)
        p.button("x")
        self.assertEqual(p.run, 2)
        self.assertTrue(any(e["event"] == "probe-run-end" and e["samples"] == 1 for e in events))

    def test_switch_cancels_and_keeps_grid(self):
        p = Probe()
        self.tap(p, 1, 16, 16)
        p.displayed()
        p.down(2, 512, 16)
        p.button("r")
        p.up(2)
        self.assertEqual(len(p.samples), 1)
        self.assertEqual(p.drags, 0)
        self.assertIsNone(p.owner)

    def test_capped_path(self):
        p = Probe()
        p.button("r")
        p.down(1, 1, 1)
        for i in range(5000):
            p.move(1, i % 1024, i % 768)
        self.assertEqual(len(p.path), 512)


if __name__ == "__main__":
    unittest.main()
