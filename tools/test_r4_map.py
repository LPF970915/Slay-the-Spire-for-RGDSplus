"""Map input policy and transformer checks; not physical touch acceptance."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "prototype/r3"
JDK = Path("C:/Program Files/Java/jdk-25/bin")


class MapTouchTests(unittest.TestCase):
    def test_gesture_and_coalesced_excursion(self):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([str(JDK / "javac.exe"), "--release", "11", "-d", directory,
                str(HERE / "java/rgds/r3/MapGesture.java"),
                str(HERE / "java/rgds/r3/TouchState.java"),
                str(HERE / "MapGestureTest.java")], check=True)
            subprocess.run([str(JDK / "java.exe"), "-cp", directory, "MapGestureTest"], check=True)

    def test_native_rules_and_animation_retained(self):
        source = (HERE / "java/rgds/r3/MapTouch.java").read_text()
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        for forbidden in ("nextRoomTransitionStart(", "setCurrMapNode(", ".counter--",
                          "DungeonMapScreen.offsetY =", "Settings.HEIGHT ="):
            self.assertNotIn(forbidden, source)
        for expected in ("MapTouch.begin(this,scrollWaitTimer);", "MapTouch.bossClick",
                         "MapTouch.scroll(targetOffsetY); updateAnimation(); return;",
                         'new String[]{"open", "close", "closeInstantly"}'):
            self.assertIn(expected, agent)
        self.assertIn("MapTouch.cancel()", (HERE / "java/rgds/r3/TouchInput.java").read_text())
        self.assertIn("TouchInput.enabled", source)
        self.assertIn("released == AbstractDungeon.dungeonMapScreen.map.bossHb", source)


if __name__ == "__main__":
    unittest.main()
