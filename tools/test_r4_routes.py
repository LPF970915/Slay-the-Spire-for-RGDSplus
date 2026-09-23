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
        self.assertIn("DualRender.dungeonOverlay($1)", block)
        self.assertEqual(block.count("$proceed($$)"), 1)
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        overlay = renderer.split("public static void dungeonOverlay(", 1)[1].split("\n    }", 1)[0]
        self.assertIn("AbstractDungeon.CurrentScreen.FTUE", overlay)
        self.assertIn("push(batch, tutorial ? 1 : 0, false)", overlay)
        self.assertIn("if (!tutorial) beginBackground(batch)", overlay)

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
        self.assertIn('"Slay the Spire for RGDSplus", "SlayTheSpireDualR4Review"', supervisor)
        self.assertIn('env["RGDS_R4_PAGE_PROBE"] = "1" if args.page_probe else "0"', supervisor)
        self.assertIn('ROOT.parent / "SlayTheSpireDualR3"', supervisor)
        self.assertIn('ROOT.parent / "Slay the Spire for RGDSplus"', supervisor)
        self.assertIn('ROOT.parent / "SlayTheSpireDualR4"', supervisor)
        launcher = (HERE / "Slay the Spire for RGDSplus.sh").read_text()
        self.assertIn('"$PORTS/Slay the Spire for RGDSplus/supervisor.py"', launcher)
        self.assertNotIn("SlayTheSpireDualR4", launcher)
        self.assertIn('--seconds 0 "$@"', launcher)
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
        self.assertIn('mapPass && screen == 0 ? -768 : 0', renderer)
        self.assertIn('hit.panel = screen', renderer)
        self.assertNotIn('recordedPanel = 1', renderer)
        self.assertIn('mapPass = state.map', renderer)
        self.assertNotIn('Settings.HEIGHT =', renderer)
        self.assertNotIn('DungeonMapScreen.offsetY =', renderer)
        self.assertIn('nativeScreenIdentity()', renderer)

    def test_transformed_hitboxes_expire_with_their_render_frame(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn('hitTransformFrames', renderer)
        self.assertIn('rememberLayout(hb, layout)', renderer)
        self.assertIn('Integer.valueOf(frames).equals(hitTransformFrames.get(hb))', renderer)
        self.assertIn('hitTransformFrames.clear()', renderer)

    def test_common_room_pages_use_native_touch_confirmation(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        touch = (HERE / "java/rgds/r3/TouchInput.java").read_text()
        self.assertIn('"U17", "U18", "U19", "U20", "U21", "U22", "U23"', renderer)
        self.assertIn('boolean nativeTouch = ownsPointer() && DualRender.nativeTouchFlow();', touch)
        self.assertIn('.contains(current)', renderer)
        self.assertIn('Settings.TOUCHSCREEN_ENABLED = nativeTouch;', touch)
        self.assertIn('Settings.isTouchScreen = nativeTouch;', touch)
        self.assertIn('Combat drag aiming and the', touch)
        self.assertIn('custom map gesture retain the mouse-style path', touch)

    def test_keyboard_and_potion_modal_keep_native_commits(self):
        keyboard = (HERE / "java/rgds/r3/TextKeyboard.java").read_text()
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        touch = (HERE / "java/rgds/r3/TouchInput.java").read_text()
        self.assertIn('SeedHelper.getValidCharacter', keyboard)
        self.assertIn('((SeedPanel)owner).confirm()', keyboard)
        self.assertIn('((RenamePopup)owner).confirm()', keyboard)
        self.assertNotIn('.flush()', keyboard)
        self.assertIn('UpperInteraction.cancelForTouch()', touch)
        self.assertIn('UpperInteraction.guardTarget', agent)
        self.assertIn('mY = 768 - rgds.r3.TouchInput.state.y', agent)
        self.assertIn('DetailControls.outsideClick', agent)
        self.assertIn('SaveSlotTouch.update(this)', agent)
        detail = (HERE / "java/rgds/r3/DetailControls.java").read_text()
        self.assertNotIn('back.update();', detail)
        self.assertIn('back.hb.update();', detail)
        diagnostic = (HERE / "java/rgds/r3/UiDiagnostics.java").read_text()
        self.assertIn('AbstractDungeon.currMapNode == null', diagnostic)
        self.assertIn('catch (RuntimeException error)', diagnostic)
        render = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn('AbstractDungeon.currMapNode == null', render)
        self.assertEqual(render.count('AbstractDungeon.getCurrRoom()'), 1)
        signature = (HERE / "java/rgds/r3/ReleaseSignature.java").read_text(encoding="utf-8")
        self.assertIn("CardCrawlGame.VERSION_NUM", signature)
        self.assertIn(" for RGDSplus", signature)
        self.assertIn("移植by Blood_roc", signature)
        self.assertIn("renderFontRightTopAligned", signature)
        self.assertIn("CurScreen.MAIN_MENU", signature)
        self.assertIn("CurScreen.PANEL_MENU", signature)
        self.assertIn("if (screen == 1) ReleaseSignature.draw(batch);", render)

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
        self.assertNotIn("--review", (HERE / "Slay the Spire for RGDSplus.sh").read_text())

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
        self.assertIn('rememberLayout(c.hb, layout)', renderer)

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

    def test_event_release_uses_native_hitbox_coordinates(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        release = renderer.split("if (TouchInput.state.justUp && hb.clickStarted)", 1)[1].split(
            "float determinant", 1)[0]
        self.assertIn("Math.round(hb.cX)", release)
        self.assertIn("Math.round(hb.cY)", release)
        self.assertNotIn("hit.tx", release)
        self.assertNotIn("hit.ty", release)
        self.assertIn("touchOrder(hb, TouchInput.state.x, TouchInput.state.y) >= 0", release)
        self.assertIn(": -10000", release)
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        self.assertIn("eventOption($1,$0,this.optionList.size())", agent)

    def test_tutorial_subclass_and_reward_banner_have_lower_routes(self):
        routes = (HERE / "java/rgds/r3/ScreenRoutes.java").read_text()
        self.assertIn('add(lower, "U27", "ui.FtueTip", "ui.MultiPageFtue"', routes)
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        banner = agent.split('owner.endsWith(".DynamicBanner")', 1)[1].split("}", 1)[0]
        self.assertIn("route(c, 1, false)", banner)
        summary = (HERE / "java/rgds/r3/PageSummary.java").read_text()
        self.assertNotIn('page.equals("U17")', summary)
        self.assertIn('TutorialTouch.update(this)', agent)
        self.assertIn('!rgds.r3.TutorialTouch.active() && $proceed()', agent)
        tutorial = (HERE / "java/rgds/r3/TutorialTouch.java").read_text()
        self.assertIn('clicked = hit && pressed == hb;', tutorial)
        self.assertIn('TouchInput.state.justUp', tutorial)

    def test_shop_inventory_is_lower_but_merchant_performance_is_upper(self):
        routes = (HERE / "java/rgds/r3/ScreenRoutes.java").read_text()
        self.assertIn('add(lower, "U20", "shop.ShopScreen")', routes)
        self.assertIn('add(upper, "U20", "shop.Merchant")', routes)
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        merchant = agent.split('simple.equals("Merchant")', 1)[1].split(
            'simple.equals("GenericEventDialog")', 1)[0]
        self.assertIn('route(c, 0, false)', merchant)
        self.assertNotIn('mirrorCall(c, 1)', merchant)
        self.assertIn('simple.equals("ShopSpeechBubble") || simple.equals("SpeechTextEffect")', agent)
        self.assertIn('"ShopSpeechBubble"', agent.split("java.util.Arrays.asList(", 1)[1].split(").contains(simple)", 1)[0])
        speech = agent.split('simple.equals("ShopSpeechBubble")', 1)[1].split(
            'simple.equals("GenericEventDialog")', 1)[0]
        self.assertIn('push($1,0,false)', speech)

    def test_startup_warmup_is_incremental_and_stops_in_gameplay(self):
        warmup = (HERE / "java/rgds/r3/StartupWarmup.java").read_text()
        render = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn("if (++idleFrames < 3) return;", warmup)
        self.assertIn("Class.forName(name, true, loader", warmup)
        self.assertIn("mode == CardCrawlGame.GameMode.SPLASH", warmup)
        self.assertIn("mode == CardCrawlGame.GameMode.CHAR_SELECT", warmup)
        self.assertIn("CardCrawlGame.dungeonTransitionScreen != null", warmup)
        self.assertIn('getClass().getSimpleName().equals("NeowRoom")', warmup)
        self.assertIn("if (complete) stopped = true;", warmup)
        self.assertIn("StartupWarmup.stopForGameplay()", render)
        self.assertIn('state.setProperty("warmup", StartupWarmup.state())', render)
        self.assertIn("images/npcs/neow/skeleton.atlas", warmup)
        self.assertIn("images/npcs/merchant/skeleton.atlas", warmup)
        self.assertIn("replacement.skeleton.setPosition(old.skeleton.getX(), old.skeleton.getY())", warmup)
        self.assertIn("images/npcs/rug/zhs.png", warmup)
        self.assertIn("new Texture(file, false)", warmup)
        self.assertIn("com.megacrit.cardcrawl.core.OverlayMenu", warmup)
        self.assertIn("com.megacrit.cardcrawl.screens.DeathScreen", warmup)
        self.assertIn("com.megacrit.cardcrawl.vfx.MapCircleEffect", warmup)
        self.assertIn("com.megacrit.cardcrawl.vfx.CardTrailEffect", warmup)

    def test_event_room_combat_uses_split_hand_layout(self):
        render = (HERE / "java/rgds/r3/DualRender.java").read_text()
        combat = render.split("private static boolean combatLayout()", 1)[1].split(
            "private static void applyLayout", 1
        )[0]
        self.assertIn("room.phase == AbstractRoom.RoomPhase.COMBAT", combat)
        self.assertIn("!room.isBattleOver", combat)
        self.assertIn("splitDungeon = dungeon && combatLayout();", render)
        self.assertIn("Event-triggered fights keep EventRoom", render)
        self.assertIn("StartupWarmup.attachNeow(this)", (HERE / "java/rgds/r3/DualAgent.java").read_text())
        self.assertIn("StartupWarmup.attachMerchant(this)", (HERE / "java/rgds/r3/DualAgent.java").read_text())

    def test_neow_credits_and_stats_follow_panel_roles(self):
        renderer = (HERE / "java/rgds/r3/DualRender.java").read_text()
        self.assertIn("Keep Neow's speech bubble at the native single-screen position", renderer)
        self.assertIn(
            "event instanceof com.megacrit.cardcrawl.neow.NeowEvent)\n            return 0;",
            renderer,
        )
        self.assertIn("public static void upperBlackOverlay", renderer)
        self.assertIn('if (!pageId.equals("U30")) return;', renderer)
        self.assertIn("batch.setColor(0, 0, 0, .72f)", renderer)
        self.assertIn('type.endsWith(".CreditsScreen")', renderer)
        self.assertIn("dimCreditsPanel(batch, 0)", renderer)
        self.assertIn("dimCreditsPanel(batch, 1)", renderer)
        agent = (HERE / "java/rgds/r3/DualAgent.java").read_text()
        neow = agent.split('simple.equals("NeowNarrationScreen")', 1)[1].split(
            'else if (simple.equals("CharacterSelectScreen"))', 1)[0]
        self.assertIn("route(c, 0, false)", neow)
        stats = agent.split(
            'simple.equals("StatsScreen") || simple.equals("RunHistoryScreen")',
            1,
        )[1].split('else if (simple.equals("PatchNotesScreen"))', 1)[0]
        self.assertIn("route(c, 1, false)", stats)
        self.assertNotIn("mirrorCall(c, 1)", stats)
        credits = agent.split('else if (simple.equals("CreditsScreen"))', 1)[1].split(
            'else if (simple.equals("PatchNotesScreen"))', 1)[0]
        self.assertIn("ImageMaster.WHITE_SQUARE_IMG", credits)
        self.assertIn("$proceed($$)", credits)


if __name__ == "__main__":
    unittest.main()
