import unittest

from analyze_frames import summarize


class FramesTest(unittest.TestCase):
    def rows(self, values, captures=()):
        return [{"monotonic_ms": i * 1000, "frame_ms": value,
                 "capture": int(i in captures)} for i, value in enumerate(values)]

    def test_slow_frames_are_not_trimmed(self):
        result = summarize(self.rows([0, 40, 40, 120, 900]))
        self.assertEqual(result["frames"], 4)
        self.assertEqual(result["max_ms"], 900)
        self.assertEqual(result["p95_ms"], 900)
        self.assertEqual(result["over_100_ms"], 2)
        self.assertEqual(result["over_250_ms"], 1)

    def test_capture_neighbors_and_explicit_window(self):
        result = summarize(self.rows([0, 40, 600, 400, 100, 45, 200], [3]),
                           1000, 5000)
        self.assertEqual(result["frames"], 2)
        self.assertEqual(result["capture_neighbor_intervals_excluded"], 3)
        self.assertEqual(result["mean_ms"], 42.5)

    def test_empty_window(self):
        with self.assertRaises(ValueError):
            summarize(self.rows([0]))


if __name__ == "__main__":
    unittest.main()
