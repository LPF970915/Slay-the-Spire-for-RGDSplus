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

    def test_review_fixtures_are_separate_and_labelled(self):
        review = (HERE / "java/rgds/r3/ReviewProbe.java").read_text()
        self.assertIn('"1".equals(System.getenv("RGDS_R4_REVIEW"))', review)
        self.assertIn('getFileName().toString().equals("SlayTheSpireDualR4Review")', review)
        self.assertIn('if (!enabled || !id.matches', review)
        supervisor = (HERE / "supervisor.py").read_text()
        self.assertIn('args.review and ROOT.name != "SlayTheSpireDualR4Review"', supervisor)
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        self.assertIn('"if (rgds.r3.ReviewProbe.enabled) return;"', agent)
        self.assertNotIn("--review", (HERE / "Slay the Spire R4 All Pages.sh").read_text())
        collector = (ROOT / "tools/capture_r4_review.py").read_text()
        self.assertIn("isolated-native-ui-specimen", collector)
        self.assertIn('physical_verified=False', collector)

    def test_preview_projection_restores_batch_and_sky_uses_bottom_band(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn('mirrorLayout = state.preview;', renderer)
        self.assertIn('mirrorCombined.set(batch.getProjectionMatrix()).mul(batch.getTransformMatrix())', renderer)
        self.assertIn('batch.setProjectionMatrix(saved.projection)', renderer)
        self.assertIn('sky.getV2() - (sky.getV2() - sky.getV()) * .025f', renderer)
        self.assertNotIn('glReadPixels', renderer)

    def test_review_restores_without_disposing_reusable_room(self):
        review = (HERE / "java/rgds/r3/ReviewProbe.java").read_text()
        self.assertNotIn("setCurrMapNode(", review)
        self.assertIn("AbstractDungeon.currMapNode = baseline;", review)
        self.assertIn("AbstractDungeon.overlayMenu.hideBlackScreen()", review)
        self.assertIn("AbstractDungeon.dynamicBanner.hide()", review)
        self.assertIn("dungeonTransitionScreen.isComplete = false", review)
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn('get(AbstractDungeon.cardRewardScreen, "chooseOne")', renderer)
        self.assertIn('baselineHand.addAll(AbstractDungeon.player.hand.group)', review)
        device = (HERE / "device.py").read_text()
        self.assertIn('sftp.posix_rename(request + ".tmp", request)', device)

    def test_selection_hand_keeps_confirm_and_inverse_hitbox(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn('equals("CardSelectConfirmButton")', renderer)
        self.assertIn('hb.cX, hb.cY, 512, 70', renderer)
        self.assertIn('AbstractDungeon.player.hand.group.contains(item)', renderer)
        self.assertIn('hitTransforms.put(c.hb, layout)', renderer)

    def test_generic_event_text_stays_upper_and_only_options_move_lower(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        dialog = renderer.split("public static int dialogTarget()", 1)[1].split(
            "public static void narration", 1)[0]
        self.assertIn("return 0;", dialog)
        self.assertIn("Generic event text and its speech animation stay on the upper panel", dialog)
        self.assertIn("public static void eventOption", renderer)
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        self.assertIn("DualRender.eventOption", agent)
        event_block = agent.split(
            'else if (simple.equals("GenericEventDialog") || simple.equals("RoomEventDialog"))',
            1)[1].split(
                'else if (simple.equals("SingleCardViewPopup") || simple.equals("SingleRelicViewPopup"))',
                1)[0]
        self.assertNotIn("mirrorDraw(c)", event_block)


if __name__ == "__main__":
    unittest.main()
