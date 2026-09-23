"""Rendering-boundary regressions; these do not claim physical panel acceptance."""

from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "prototype/r3/java/rgds/r3"


class CombatVisualTests(unittest.TestCase):
    def test_flight_geometry(self):
        jdk = Path("C:/Program Files/Java/jdk-25/bin")
        classes = ROOT / "prototype/r3/build/classes"
        subprocess.run([str(jdk / "javac.exe"), "--release", "11", "-d", str(classes),
                        str(JAVA / "CardFlightPath.java"),
                        str(ROOT / "prototype/r3/CardFlightPathTest.java")], check=True)
        subprocess.run([str(jdk / "java.exe"), "-cp", str(classes),
                        "CardFlightPathTest"], check=True)

    def test_visual_render_does_not_add_rules_or_hitboxes(self):
        flight = (JAVA / "CardFlight.java").read_text()
        render = (JAVA / "DualRender.java").read_text()
        self.assertEqual(flight.count("card.render(batch)"), 1)
        for call in ("card.update(", "card.use(", "card.makeCopy(", "player.useCard("):
            self.assertNotIn(call, flight)
        self.assertIn("f != null && !f.started", flight)
        self.assertIn("if (!TouchInput.enabled || !active || CardFlight.visual()) return", render)
        self.assertIn("card.current_x = x; card.current_y = y;", flight)
        self.assertIn("card.drawScale = scale; card.angle = angle;", flight)
        self.assertIn("new UiTransform(1, 0, -816)", render)
        self.assertIn("f.arrived = f.age >= CardFlightPath.DURATION", flight)

    def test_pooled_trails_keep_origin_and_cursor_allows_pad(self):
        agent = (JAVA / "DualAgent.java").read_text()
        effects = (JAVA / "CombatEffects.java").read_text()
        touch = (JAVA / "TouchInput.java").read_text()
        self.assertIn('getDeclaredMethod("init").insertAfter("rgds.r3.CombatEffects.trail(this);")', agent)
        self.assertIn("kinds.remove(effect)", effects)
        self.assertIn("soul.group == AbstractDungeon.player.drawPile", effects)
        self.assertIn("soul.group == AbstractDungeon.player.discardPile", effects)
        self.assertIn('return "native";', effects)
        self.assertIn("if (pad) touchCursor = false", touch)
        self.assertIn("touchCursor = true", touch)


if __name__ == "__main__":
    unittest.main()
