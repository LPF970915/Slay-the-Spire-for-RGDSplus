"""Prove that the lifecycle gate actually catches the regression it guards."""

from pathlib import Path
import tempfile
import unittest

from test_touch_contract import P1, validate_source


class ContractChecks(unittest.TestCase):
    def check_mutation(self, old, new):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("supervisor.py", "touch_mode.py", "device_input.py", "app.py"):
                text = (P1 / name).read_text(encoding="utf-8")
                if name == "supervisor.py":
                    self.assertIn(old, text)
                    text = text.replace(old, new, 1)
                (root / name).write_text(text, encoding="utf-8")
            with self.assertRaises((AssertionError, IndexError)):
                validate_source(root)

    def test_reference_passes(self):
        validate_source()

    def test_missing_activation_fails(self):
        self.check_mutation('enable_mode(state["touch_previous"], log=touch_log)', "pass")

    def test_missing_recovery_restore_fails(self):
        self.check_mutation('restore_mode(state.get("touch_previous"))', "pass")

    def test_missing_normal_restore_fails(self):
        self.check_mutation('restore_mode(state.get("touch_previous"), log=touch_log)', "pass")

    def test_activation_before_persist_fails(self):
        self.check_mutation(
            'temporary.replace(state_path)\n        enable_mode(state["touch_previous"], log=touch_log)',
            'enable_mode(state["touch_previous"], log=touch_log)\n        temporary.replace(state_path)')


if __name__ == "__main__":
    unittest.main()
