"""Ensure profiling overrides stay isolated and fail closed on launcher drift."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype/r3"))
from launch_profile import configure
from diagnostic_io import archive_runtime
from analyze_r3_perf import analyze


class ProfileTests(unittest.TestCase):
    def test_isolated_overrides(self):
        original = (ROOT / "packaging/launch.sh").read_text(encoding="utf-8")
        result = configure(original)
        self.assertIn("768\\n24\\n", original)
        self.assertNotIn("768\\n24\\n", result)
        self.assertIn('${RGDS_R3_FPS:-30}', result)
        self.assertIn('"-XX:+Use${RGDS_R3_GC:-Serial}GC"', result)
        self.assertIn("-Xlog:gc*,safepoint", result)
        self.assertIn('"-XX:TieredStopAtLevel=${RGDS_R4_JIT_TIER:-4}"', result)
        self.assertIn('"-Xms${RGDS_R3_XMS:-64}M"', result)
        self.assertIn("librgds-dual.so", result)
        self.assertEqual(result.count('"-javaagent:$APP_DIR/rgds-dual-r3.jar"'), 1)
        self.assertEqual(
            original,
            (ROOT / "packaging/launch.sh").read_text(encoding="utf-8"),
        )

    def test_launcher_drift_rejected(self):
        with self.assertRaises(ValueError):
            configure("")

    def test_deploy_contains_runtime_helper(self):
        device = (ROOT / "prototype/r3/device.py").read_text(encoding="utf-8")
        supervisor = (ROOT / "prototype/r3/supervisor.py").read_text(encoding="utf-8")
        self.assertIn('"diagnostic_io.py": HERE/"diagnostic_io.py"', device)
        self.assertIn('archive_runtime(ROOT, state.get("runtime"))', supervisor)
        self.assertEqual(supervisor.count('archive_runtime(ROOT, state.get("runtime"))'), 2)

    def test_runtime_archive_and_repeat(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            root = base / "app"
            (root / "logs").mkdir(parents=True)
            runtime = base / "rgds-sts-r3-test"
            runtime.mkdir()
            (runtime / "state.xml").write_text("<state/>")
            (runtime / "capture.request").write_text("capture")
            (runtime / "page-result.txt").write_text("opened")
            (runtime / "page.request").write_text("u14")
            (runtime / "page.request.tmp").write_text("u15")
            archive_runtime(root, runtime, base)
            self.assertEqual((root / "logs/state.xml").read_text(), "<state/>")
            self.assertEqual((root / "logs/page-result.txt").read_text(), "opened")
            self.assertFalse(runtime.exists())
            archive_runtime(root, runtime, base)

    def test_archive_rejects_outside_and_unexpected_entries(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            root = base / "app"
            (root / "logs").mkdir(parents=True)
            with self.assertRaises(ValueError):
                archive_runtime(root, base, base)
            runtime = base / "rgds-sts-r3-test"
            runtime.mkdir()
            (runtime / "state.xml").write_text("keep valid file too")
            (runtime / "unexpected.txt").write_text("keep")
            with self.assertRaises(ValueError):
                archive_runtime(root, runtime, base)
            self.assertTrue((runtime / "unexpected.txt").exists())
            self.assertTrue((runtime / "state.xml").exists())

    def test_gc_join_retains_unexplained_slow_frames(self):
        rows = [{"monotonic_ms": t, "frame_ms": d, "capture": c}
                for t, d, c in [(1000, 33, 0), (1120, 120, 0),
                                 (1300, 180, 0), (1500, 200, 1)]]
        result = analyze(rows, "[r3-perf] mono_ms=1000 uptime_ms=100\n",
                         "[200ms][info][gc] GC(0) Pause Young 10M->2M(20M) 12.000ms\n")
        self.assertEqual(len(result["slow_frames"]), 1)
        self.assertEqual(result["slow_frames"][0]["overlapping_gc"][0]["duration_ms"], 12)
        result = analyze(rows[:3], "[r3-perf] mono_ms=1000 uptime_ms=100\n", "")
        self.assertEqual(len(result["slow_frames"]), 2)
        self.assertFalse(result["slow_frames"][0]["overlapping_gc"])


if __name__ == "__main__":
    unittest.main()
