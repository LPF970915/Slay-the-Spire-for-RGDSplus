"""Preserve historical P1 geometry and verify the new R4 sticky drag policy."""

from pathlib import Path
import random
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype/p1"))
from geometry import pick, scene_targets


class CombatGeometryTests(unittest.TestCase):
    def test_neutral_hand_entry(self):
        jdk = Path("C:/Program Files/Java/jdk-25/bin")
        classes = ROOT / "prototype/r3/build/classes"
        subprocess.run([str(jdk / "javac.exe"), "--release", "11", "-d", str(classes),
                        str(ROOT / "prototype/r3/java/rgds/r3/HandFocus.java"),
                        str(ROOT / "prototype/r3/HandFocusTest.java")], check=True)
        subprocess.run([str(jdk / "java.exe"), "-cp", str(classes), "HandFocusTest"], check=True)
        combat = (ROOT / "prototype/r3/java/rgds/r3/CombatTouch.java").read_text()
        self.assertIn("if (!TouchInput.enabled) return false", combat)
        self.assertIn("!player.endTurnQueued && !player.isEndingTurn", combat)
        self.assertIn("!AbstractDungeon.actionManager.turnHasEnded", combat)

    def test_sticky_drag(self):
        jdk = Path("C:/Program Files/Java/jdk-25/bin")
        classes = ROOT / "prototype/r3/build/classes"
        subprocess.run([str(jdk / "javac.exe"), "--release", "11", "-d", str(classes),
                        str(ROOT / "prototype/r3/java/rgds/r3/DragAim.java"),
                        str(ROOT / "prototype/r3/DragAimTest.java")], check=True)
        result = subprocess.run([str(jdk / "java.exe"), "-cp", str(classes), "DragAimTest"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_p1_java_agreement(self):
        rng = random.Random(421)
        rows = []
        for scene in range(5):
            targets = scene_targets(scene, 1)
            for _ in range(400):
                origin = (rng.randrange(70, 954), rng.randrange(1200, 1500))
                pointer = (rng.randrange(3, 1021), rng.randrange(819, 1510))
                previous = rng.randrange(-1, len(targets))
                selected, _ = pick(origin, pointer, targets,
                                   targets[previous].uid if previous >= 0 else None)
                expected = next((i for i, t in enumerate(targets) if t.uid == selected), -1)
                values = [*origin, *pointer, previous, expected, len(targets)]
                for t in targets:
                    values.extend((t.x, t.y, t.w, t.h))
                rows.append(" ".join(map(str, values)))
        jdk = Path("C:/Program Files/Java/jdk-25/bin")
        classes = ROOT / "prototype/r3/build/classes"
        subprocess.run([str(jdk / "javac.exe"), "--release", "11", "-cp", str(classes),
                        "-d", str(classes), str(ROOT / "prototype/r3/AimPickerTest.java")], check=True)
        result = subprocess.run([str(jdk / "java.exe"), "-cp", str(classes), "AimPickerTest"],
                                input=str(len(rows)) + "\n" + "\n".join(rows),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
