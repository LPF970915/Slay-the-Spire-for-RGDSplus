from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from touch_mode import read_mode, enable_mode, restore_mode


class TouchModeTests(unittest.TestCase):
    def test_both_known_modes_restore(self):
        for previous in ("0", "1"):
            with self.subTest(previous=previous), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "tpctrl"
                path.write_text(previous + "\n")
                saved = read_mode(path)
                self.assertTrue(enable_mode(saved, path, lambda _: None))
                self.assertEqual(path.read_text(), "0\n")
                self.assertTrue(restore_mode(saved, path, lambda _: None))
                self.assertEqual(path.read_text(), previous + "\n")

    def test_zero_still_gets_written(self):
        path = Mock()
        path.read_text.return_value = "0\n"
        self.assertTrue(enable_mode("0", path, lambda _: None))
        path.write_text.assert_called_once_with("0\n")

    def test_unknown_mode_is_never_written(self):
        path = Mock()
        path.read_text.return_value = "unsupported\n"
        previous = read_mode(path, lambda _: None)
        self.assertIsNone(previous)
        self.assertFalse(enable_mode(previous, path))
        self.assertFalse(restore_mode(previous, path))
        path.write_text.assert_not_called()

    def test_missing_interface(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing"
            previous = read_mode(path, lambda _: None)
            self.assertIsNone(previous)
            self.assertFalse(enable_mode(previous, path))
            self.assertFalse(path.exists())

    def test_do_not_overwrite_later_mode_change(self):
        path = Mock()
        path.read_text.return_value = "1\n"
        self.assertFalse(restore_mode("0", path, lambda _: None))
        path.write_text.assert_not_called()

    def test_write_failure_is_reported(self):
        path = Mock()
        path.write_text.side_effect = OSError("read only")
        messages = []
        self.assertFalse(enable_mode("1", path, messages.append))
        self.assertTrue(any("enable failed" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
