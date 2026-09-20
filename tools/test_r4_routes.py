"""Guard R4 routing scope and opt-in gallery isolation; not visual acceptance."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "prototype/r3"


class RouteContracts(unittest.TestCase):
    def test_active_page_does_not_follow_last_render_call(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        page = renderer.split("public static void page(", 1)[1].split("\n    }", 1)[0]
        self.assertNotIn("pageId =", page)
        self.assertIn("ScreenRoutes.dungeonId(nativeScreen, room)", renderer)
        self.assertIn('cls.getDeclaredMethod(name, SpriteBatch.class)', renderer)
        self.assertIn('eventRoutes.put(type, target)', renderer)

    def test_no_second_native_black_overlay_render(self):
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        block = agent.split('method.equals("renderBlackScreen")', 1)[1].split("else if", 1)[0]
        self.assertIn("mirrorCall(c, 0)", block)
        self.assertNotIn("$proceed", block)

    def test_gallery_is_opt_in_and_uses_native_menu_only(self):
        probe = (HERE / "java/rgds/r3/PageProbe.java").read_text()
        self.assertIn('"1".equals(System.getenv("RGDS_R4_PAGE_PROBE"))', probe)
        self.assertIn('if (!enabled ||', probe)
        self.assertIn('menu.screen != MainMenuScreen.CurScreen.MAIN_MENU', probe)
        self.assertLess(probe.index("menu.panelScreen.open(parent)"),
                        probe.index("menu.cardLibraryScreen.open()"))
        for forbidden in ("Class.forName", ".invoke(", "Runtime.getRuntime", "new DeathScreen",
                          "new VictoryScreen", "setCurrMapNode", "new RestRoom", "new ShopRoom"):
            self.assertNotIn(forbidden, probe)
        self.assertIn('AbstractDungeon.screen != AbstractDungeon.CurrentScreen.NONE', probe)
        self.assertIn('AbstractDungeon.dungeonMapScreen.open(false)', probe)
        supervisor = (HERE / "supervisor.py").read_text()
        self.assertIn('args.page_probe and ROOT.name != "SlayTheSpireDualR4"', supervisor)
        self.assertIn('env["RGDS_R4_PAGE_PROBE"] = "1" if args.page_probe else "0"', supervisor)
        self.assertIn('ROOT.parent / "SlayTheSpireDualR3"', supervisor)
        self.assertIn('ROOT.parent / "SlayTheSpireDualR4"', supervisor)
        launcher = (HERE / "Slay the Spire R4 All Pages.sh").read_text()
        self.assertIn("SlayTheSpireDualR4/supervisor.py", launcher)
        self.assertNotIn("--page-probe", launcher)
        ast.parse((HERE / "device.py").read_text())

    def test_build_checks_actual_native_enums(self):
        test = (HERE / "TransformTest.java").read_text()
        self.assertIn('AbstractDungeon$CurrentScreen', test)
        self.assertIn('MainMenuScreen$CurScreen', test)
        self.assertIn('actual.equals(policy.keySet())', test)
        self.assertIn('Page scope missing', test)

    def test_continuous_map_keeps_native_input_space(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn('mapPass ? 1536 : 768', renderer)
        self.assertIn('mapPass && screen == 1 ? -768 : 0', renderer)
        self.assertIn('mapPass = state.map', renderer)
        self.assertNotIn('Settings.HEIGHT =', renderer)
        self.assertNotIn('DungeonMapScreen.offsetY =', renderer)
        self.assertIn('nativeScreenIdentity()', renderer)

    def test_targeting_reuses_native_sprites_and_single_animation(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        targeting = renderer.split("public static void targeting(", 1)[1].split(
            "public static void finish(", 1)[0]
        for token in ("ImageMaster.TARGET_UI_CIRCLE", "ImageMaster.TARGET_UI_ARROW",
                      'get(AbstractPlayer.class, "ARROW_COLOR")', "Interpolation.elasticOut",
                      "AimCurve.panelY", "lastAimFrame != frames"):
            self.assertIn(token, targeting)
        self.assertNotIn("WHITE_SQUARE_IMG", targeting)
        self.assertNotIn("GOLD_COLOR", targeting)
        self.assertNotIn("if (target == 0)", targeting)
        self.assertLess(targeting.index("aimTimer = Math.min"),
                        targeting.index("for (int target = 0; target < 2"))
        curve = (HERE / "java/rgds/r3/AimCurve.java").read_text()
        self.assertIn("Bezier.quadratic(", curve)


if __name__ == "__main__":
    unittest.main()
