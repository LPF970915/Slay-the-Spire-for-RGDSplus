package rgds.r3;

import java.io.ByteArrayInputStream;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import javassist.*;
import javassist.expr.ExprEditor;
import javassist.expr.MethodCall;
import javassist.expr.FieldAccess;

/** Game-free method routing. The original game and stable adapter are not edited. */
public final class DualAgent {
    private static final String CORE = "com/megacrit/cardcrawl/";
    public static final java.util.Set<String> SMALL_CONTROLS = new java.util.LinkedHashSet<String>(
            java.util.Arrays.asList("MenuButton", "MenuCancelButton", "CancelButton", "ConfirmButton",
                    "GridSelectConfirmButton", "ReturnToMenuButton", "UnlockConfirmButton",
                    "CardSelectConfirmButton", "SkipCardButton"));
    public static final java.util.Map<String, String> COMBAT_EFFECTS = new java.util.LinkedHashMap<>();
    static {
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/GameDeckGlowEffect", "draw");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/DiscardGlowEffect", "discard");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/RefreshEnergyEffect", "energy");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/EndTurnGlowEffect", "end");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/EndTurnLongPressBarFlashEffect", "end");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/ExhaustPileParticle", "exhaust");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/combat/DeckPoofParticle", "lower");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/CardTrailEffect", "native");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/cardManip/CardGlowBorder", "hand");
        COMBAT_EFFECTS.put("com/megacrit/cardcrawl/vfx/cardManip/CardFlashVfx", "hand");
    }

    public static void premain(String args, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            public byte[] transform(ClassLoader loader, String name, Class<?> cls,
                                    ProtectionDomain domain, byte[] bytes) {
                if (!name.startsWith(CORE) &&
                    !name.equals("com/badlogic/gdx/backends/lwjgl/LwjglApplicationConfiguration") &&
                    !name.equals("com/badlogic/gdx/backends/lwjgl/LwjglInput") &&
                    !name.equals("com/badlogic/gdx/graphics/g2d/SpriteBatch"))
                    return null;
                String simple = name.substring(name.lastIndexOf('/') + 1);
                boolean registered = ScreenRoutes.id(name.replace('/', '.')) != null;
                if (!registered && !COMBAT_EFFECTS.containsKey(name) && !SMALL_CONTROLS.contains(simple) && !java.util.Arrays.asList("CardCrawlGame", "AbstractDungeon", "AbstractPlayer",
                        "MainMenuScreen", "LwjglApplicationConfiguration", "OverlayMenu",
                        "AbstractMonster", "AbstractCreature", "Hitbox", "SpriteBatch",
                        "CharacterOption", "EventRoom", "TitleBackground", "DungeonMap",
                        "MapCircleEffect", "CardGroup", "StoreRelic", "StorePotion", "Metrics",
                        "InfiniteSpeechBubble", "SpeechTextEffect", "ShopSpeechBubble",
                        "InputHelper", "LwjglInput",
                        "GameCursor", "AbstractCard", "Soul", "SaveSlot", "ProceedButton").contains(simple)) return null;
                CtClass target = null;
                try {
                    ClassPool pool = new ClassPool(true);
                    pool.insertClassPath(new LoaderClassPath(loader));
                    target = pool.makeClass(new ByteArrayInputStream(bytes));
                    if (COMBAT_EFFECTS.containsKey(name)) {
                        String kind = COMBAT_EFFECTS.get(name);
                        if (simple.equals("CardTrailEffect"))
                            target.getDeclaredMethod("init").insertAfter("rgds.r3.CombatEffects.trail(this);");
                        if (simple.equals("DeckPoofParticle"))
                            for (CtConstructor ctor : target.getDeclaredConstructors())
                                ctor.insertAfter("rgds.r3.CombatEffects.particle(this,$1);");
                        for (CtMethod method : target.getDeclaredMethods()) {
                            if (!method.getName().equals("render")) continue;
                            if (simple.equals("CardTrailEffect"))
                                method.insertBefore("if (rgds.r3.CombatEffects.hidden(this)) return;");
                            method.insertBefore("rgds.r3.CombatEffects.begin($1,this,\"" + kind + "\");");
                            method.insertAfter("rgds.r3.DualRender.pop($1);", true);
                        }
                    } else if (simple.equals("GameCursor")) {
                        target.getDeclaredMethod("render").insertBefore(
                                "if (rgds.r3.CombatEffects.cursor()) return;");
                    } else if (simple.equals("AbstractCard")) {
                        target.getDeclaredMethod("isHoveredInHand").insertBefore(
                                "if (rgds.r3.TouchInput.ownsPointer() && "
                                + "com.megacrit.cardcrawl.dungeons.AbstractDungeon.screen == "
                                + "com.megacrit.cardcrawl.dungeons.AbstractDungeon.CurrentScreen.HAND_SELECT) "
                                + "return rgds.r3.DualRender.touchHitAt((float)rgds.r3.TouchInput.state.x,"
                                + "(float)rgds.r3.TouchInput.state.y) == hb;");
                        CtMethod render = target.getDeclaredMethod("render", new CtClass[]{
                                pool.get("com.badlogic.gdx.graphics.g2d.SpriteBatch"), CtClass.booleanType});
                        render.insertBefore("if (rgds.r3.CardFlight.hide(this)) return;");
                        target.getDeclaredMethod("renderHoverShadow").insertBefore(
                                "if (rgds.r3.CardFlight.hide(this)) return;");
                        target.getDeclaredMethod("renderOuterGlow").insertBefore(
                                "if (rgds.r3.CardFlight.hide(this)) return;");
                        target.getDeclaredMethod("isOnScreen").insertBefore(
                                "if (rgds.r3.CardFlight.visual(this)) return true;");
                    } else if (simple.equals("Soul")) {
                        target.getDeclaredMethod("update").insertBefore("rgds.r3.CombatEffects.soulBegin(this);");
                        target.getDeclaredMethod("update").insertAfter("rgds.r3.CombatEffects.soulEnd();", true);
                        target.getDeclaredMethod("render").insertBefore(
                                "rgds.r3.CombatEffects.begin($1,this,\"soul\");");
                        target.getDeclaredMethod("render").insertAfter("rgds.r3.DualRender.pop($1);", true);
                    } else if (simple.equals("Metrics")) {
                        target.getDeclaredMethod("run").insertBefore(
                                "if (rgds.r3.ReviewProbe.enabled) return;");
                    } else if (simple.equals("SpriteBatch")) {
                        target.getDeclaredMethod("flush").instrument(new ExprEditor() {
                            public void edit(MethodCall c) throws CannotCompileException {
                                if (c.getClassName().equals("com.badlogic.gdx.graphics.Mesh") &&
                                        c.getMethodName().equals("render"))
                                    c.replace("{ $proceed($$); if (rgds.r3.DualRender.mirrorBatch()) {"
                                        + "rgds.r3.DualRender.lowerBackgroundViewport(this);"
                                        + "try { $proceed($$); } finally {"
                                        + "rgds.r3.DualRender.restoreBackgroundViewport(this); } } }");
                            }
                        });
                    } else if (simple.equals("LwjglApplicationConfiguration")) {
                        target.makeClassInitializer().insertAfter(
                                "disableAudio = \"1\".equals(System.getenv(\"RGDS_STS_SILENT\"));");
                    } else if (simple.equals("LwjglInput")) {
                        for (CtMethod method : target.getDeclaredMethods()) {
                            String getter = method.getName();
                            if (getter.equals("getX") || getter.equals("getY") ||
                                    getter.equals("getDeltaX") || getter.equals("getDeltaY")) {
                                String field = getter.equals("getX") ? "x" : getter.equals("getY") ? "y" :
                                        getter.equals("getDeltaX") ? "dx" : "dy";
                                method.insertBefore("if (rgds.r3.TouchInput.ownsPointer()) return rgds.r3.TouchInput.state." + field + ";");
                            } else if (getter.equals("isButtonPressed")) {
                                method.insertBefore("if (rgds.r3.TouchInput.enabled) return $1 == 0 && rgds.r3.TouchInput.state.down;");
                            } else if (getter.equals("isTouched")) {
                                method.insertBefore("if (rgds.r3.TouchInput.enabled) return rgds.r3.TouchInput.state.down;");
                            } else if (getter.equals("justTouched")) {
                                method.insertBefore("if (rgds.r3.TouchInput.enabled) return rgds.r3.TouchInput.state.justDown;");
                            } else if (getter.equals("setCursorPosition")) {
                                method.insertBefore("if (rgds.r3.TouchInput.ownsPointer()) return;");
                            }
                        }
                    } else if (simple.equals("InputHelper")) {
                        target.instrument(new ExprEditor() {
                            public void edit(FieldAccess field) throws CannotCompileException {
                                if (field.isWriter() && field.getClassName().endsWith(".Settings") &&
                                        field.getFieldName().equals("isControllerMode"))
                                    field.replace("{ $proceed($1 && !rgds.r3.TouchInput.ownsPointer()); }");
                            }
                        });
                        target.getDeclaredMethod("updateFirst").insertBefore(
                                "if (rgds.r3.TouchInput.enabled) {"
                                + "if (rgds.r3.TouchInput.poll()) { isPrevMouseDown = false;"
                                + "isMouseDown = false; justClickedLeft = false; justReleasedClickLeft = false; }"
                                + "if (rgds.r3.TouchInput.state.justDown &&"
                                + " com.megacrit.cardcrawl.core.Settings.isControllerMode) leaveControllerMode();"
                                + "touchDown = false; touchUp = false; }");
                        target.getDeclaredMethod("updateFirst").insertAfter(
                                "if (rgds.r3.TouchInput.ownsPointer()) {"
                                + "mX = rgds.r3.TouchInput.state.x;"
                                + "mY = 768 - rgds.r3.TouchInput.state.y;"
                                + "justClickedLeft = rgds.r3.TouchInput.state.justDown;"
                                + "justReleasedClickLeft = rgds.r3.TouchInput.state.justUp;"
                                + "isMouseDown = rgds.r3.TouchInput.state.down; }"
                                + "else { justClickedLeft = false; justReleasedClickLeft = false; }"
                                + "if (com.megacrit.cardcrawl.core.CardCrawlGame.mode =="
                                + " com.megacrit.cardcrawl.core.CardCrawlGame.GameMode.CHAR_SELECT"
                                + " && com.megacrit.cardcrawl.helpers.controller.CInputActionSet.cancel.isJustPressed()"
                                + " && !com.megacrit.cardcrawl.core.CardCrawlGame.mainMenuScreen.abandonPopup.shown)"
                                + " pressedEscape = true;");
                    } else if (simple.equals("CardCrawlGame")) {
                        CtMethod render = target.getDeclaredMethod("render");
                        render.instrument(new ExprEditor() {
                            public void edit(MethodCall c) throws CannotCompileException {
                                String owner = c.getClassName(), method = c.getMethodName();
                                if (owner.equals("com.badlogic.gdx.graphics.g2d.SpriteBatch")
                                        && method.equals("begin"))
                                    c.replace("{ $proceed($$); rgds.r3.DualRender.begin($0); }");
                                else if (owner.equals("com.badlogic.gdx.graphics.g2d.SpriteBatch")
                                        && method.equals("end"))
                                    c.replace("{ rgds.r3.DualRender.finish($0); $proceed($$); }");
                                else if (method.equals("renderBlackFadeScreen"))
                                    c.replace("{ rgds.r3.DualRender.push($1, 0, false); $proceed($$);"
                                            + "rgds.r3.DualRender.pop($1);"
                                            + "rgds.r3.DualRender.fadeLower($1); }");
                                else if (method.equals("render") && owner.endsWith(".TipHelper"))
                                    routeExpression(c, "rgds.r3.DualRender.tipTarget()");
                                else if (method.equals("render") &&
                                    (owner.endsWith("SingleCardViewPopup")
                                     || owner.endsWith("SingleRelicViewPopup")))
                                    route(c, 1, false);
                            }
                        });
                        render.insertBefore("rgds.r3.PerfProbe.renderBegin();");
                        render.insertAfter("rgds.r3.PerfProbe.renderEnd();", true);
                        CtMethod update = target.getDeclaredMethod("update");
                        update.insertBefore("rgds.r3.DualRender.logicTick(); rgds.r3.PerfProbe.updateBegin();");
                        update.insertAfter("rgds.r3.PageProbe.poll();");
                        update.insertAfter("rgds.r3.PerfProbe.updateEnd();", true);
                    } else if (simple.equals("AbstractDungeon")) {
                        target.getDeclaredMethod("render").instrument(new ExprEditor() {
                            public void edit(MethodCall c) throws CannotCompileException {
                                String owner = c.getClassName(), method = c.getMethodName();
                                if (method.equals("renderCombatRoomBg") ||
                                        method.equals("renderCampfireRoom") || method.equals("renderEventRoom")) {
                                    c.replace("{ rgds.r3.DualRender.push($1,0,false);"
                                        + "rgds.r3.DualRender.beginBackground($1);"
                                        + "try { $proceed($$); } finally {"
                                        + "rgds.r3.DualRender.endBackground($1);"
                                        + "rgds.r3.DualRender.pop($1); } }");
                                } else if (method.equals("renderCombatRoomFg")) {
                                    route(c, 1, false);
                                } else if (method.equals("render") && owner.endsWith(".AbstractRoom")) {
                                    routeExpression(c, "rgds.r3.DualRender.roomTarget($0)");
                                } else if (method.equals("renderAboveTopPanel") && owner.endsWith(".AbstractRoom")) {
                                    routeExpression(c, "rgds.r3.DualRender.roomTarget($0)");
                                } else if (method.equals("renderBlackScreen")) {
                                    c.replace("{ rgds.r3.DualRender.dungeonOverlay($1);"
                                        + "try { $proceed($$); } finally {"
                                        + "rgds.r3.DualRender.endBackground($1);"
                                        + "rgds.r3.DualRender.pop($1); } }");
                                } else if (method.equals("render") &&
                                        (owner.endsWith(".OverlayMenu") ||
                                         owner.endsWith(".CancelButton") ||
                                         owner.endsWith(".DynamicBanner"))) {
                                    route(c, 1, false);
                                }
                            }
                        });
                    } else if (simple.equals("Hitbox")) {
                        target.getDeclaredMethod("render").insertBefore(
                                "rgds.r3.DualRender.recordTouchHit(this, $1);");
                        target.getDeclaredMethod("update", new CtClass[0]).insertBefore(
                                "rgds.r3.DualRender.pointerBegin(this);");
                        target.getDeclaredMethod("update", new CtClass[0]).insertAfter(
                                "rgds.r3.DualRender.pointerEnd();", true);
                    } else if (simple.equals("OverlayMenu")) {
                        target.getDeclaredMethod("render").instrument(new ExprEditor() {
                            public void edit(MethodCall c) throws CannotCompileException {
                                if (!c.getMethodName().equals("render")) return;
                                String owner = c.getClassName(), kind = null;
                                if (owner.endsWith(".EnergyPanel")) kind = "energy";
                                if (owner.endsWith(".EndTurnButton")) kind = "end";
                                if (owner.endsWith(".DrawPilePanel")) kind = "draw";
                                if (owner.endsWith(".DiscardPilePanel")) kind = "discard";
                                if (kind != null)
                                    c.replace("{ rgds.r3.DualRender.pushControl($1,$0,\"" + kind + "\");"
                                        + "try { $proceed($$); } finally { rgds.r3.DualRender.pop($1); } }");
                            }
                        });
                    } else if (simple.equals("AbstractCreature")) {
                        info(target.getDeclaredMethod("renderHealth"), "health");
                        for (CtMethod method : target.getDeclaredMethods()) {
                            if (!method.getName().equals("renderReticle")) continue;
                            method.insertBefore("rgds.r3.CombatEffects.reticle($1);");
                            method.insertAfter("rgds.r3.DualRender.pop($1);", true);
                        }
                    } else if (simple.equals("AbstractMonster")) {
                        for (String method : new String[]{"renderIntent", "renderDamageRange",
                                "renderIntentVfxBehind", "renderIntentVfxAfter"})
                            info(target.getDeclaredMethod(method), "intent");
                    } else if (simple.equals("AbstractPlayer")) {
                        target.getDeclaredMethod("updateControllerInput").insertBefore(
                                "if (rgds.r3.CombatTouch.neutralHand(this)) return;");
                        target.getDeclaredMethod("useCard").insertAfter("rgds.r3.CardFlight.used($1);");
                        target.getDeclaredMethod("updateInput").insertBefore(
                                "{ int action = rgds.r3.CombatTouch.update(this);"
                                + "if (action != 0) {"
                                + "hoveredMonster = rgds.r3.CombatTouch.target;"
                                + "if (action == 2) { playCard();"
                                + "rgds.r3.CombatTouch.committed(); releaseCard(); } return; } }");
                        target.getDeclaredMethod("renderHand").insertBefore(
                                "rgds.r3.DualRender.push($1, 1, true);");
                        target.getDeclaredMethod("renderHand").insertAfter(
                                "rgds.r3.DualRender.pop($1);", true);
                        // The native target reticle remains with the actual enemy.
                        target.getDeclaredMethod("renderHoverReticle").insertBefore(
                                "rgds.r3.DualRender.push($1, 0, false);");
                        target.getDeclaredMethod("renderHoverReticle").insertAfter(
                                "rgds.r3.DualRender.pop($1);", true);
                        target.getDeclaredMethod("renderTargetingUi").setBody(
                                "{ rgds.r3.DualRender.targeting($1, this); }");
                    } else if (simple.equals("MainMenuScreen")) {
                        target.getDeclaredMethod("render").instrument(new ExprEditor() {
                            public void edit(MethodCall c) throws CannotCompileException {
                                if (c.getClassName().endsWith(".TitleBackground") &&
                                        c.getMethodName().equals("render")) route(c, 0, false);
                            }
                        });
                    }
                    pageRouting(target, simple);
                    if (registered) {
                        boolean mirror = ScreenRoutes.MIRROR.containsKey(target.getName());
                        int output = ScreenRoutes.UPPER.containsKey(target.getName()) ? 0 : 1;
                        String outputExpression = simple.equals("GenericEventDialog") || simple.equals("RoomEventDialog")
                                ? "rgds.r3.DualRender.dialogTarget()" : String.valueOf(output);
                        CtMethod method = target.getDeclaredMethod("render",
                                new CtClass[]{pool.get("com.badlogic.gdx.graphics.g2d.SpriteBatch")});
                        method.insertBefore("rgds.r3.DualRender.page($1," + outputExpression + "," + mirror +
                                ",\"" + ScreenRoutes.id(target.getName()) + "\",\"" + target.getName() + "\");");
                        method.insertAfter("rgds.r3.DualRender.endPage($1," + mirror + ");", true);
                    }
                    System.out.println("[rgds-r3] instrumented " + name);
                    return target.toBytecode();
                } catch (Throwable error) {
                    System.err.println("[rgds-r3] TRANSFORM FAILED " + name);
                    error.printStackTrace();
                    // A half-routed scene is not a usable fallback.
                    Runtime.getRuntime().halt(73);
                    return null;
                } finally {
                    if (target != null) target.detach();
                }
            }
        }, true);
    }

    private static void pageRouting(CtClass target, String simple) throws Exception {
        if (simple.equals("MultiPageFtue")) {
            target.getDeclaredMethod("update").insertBefore("rgds.r3.TutorialTouch.update(this);");
            target.getDeclaredMethod("update").instrument(new ExprEditor() {
                public void edit(FieldAccess field) throws CannotCompileException {
                    if (field.isReader() && field.getClassName().endsWith(".InputHelper") &&
                            field.getFieldName().equals("justClickedLeft"))
                        field.replace("{ $_ = rgds.r3.TutorialTouch.click($proceed()); }");
                }
            });
        } else if (simple.equals("ProceedButton")) {
            CtMethod update = target.getDeclaredMethod("update");
            update.instrument(new ExprEditor() {
                public void edit(FieldAccess field) throws CannotCompileException {
                    if (field.isReader() && field.getClassName().endsWith(".Hitbox") &&
                            field.getFieldName().equals("clicked"))
                        field.replace("{ $_ = !rgds.r3.TutorialTouch.active() && $proceed(); }");
                }
                public void edit(MethodCall call) throws CannotCompileException {
                    if (call.getClassName().endsWith(".CInputAction") &&
                            call.getMethodName().equals("isJustPressed"))
                        call.replace("{ $_ = !rgds.r3.TutorialTouch.active() && $proceed($$); }");
                }
            });
            update.insertAfter("if (rgds.r3.TutorialTouch.active()) hb.clickStarted = hb.clicked = false;");
        } else if (simple.equals("SaveSlot")) {
            target.getDeclaredMethod("update").insertBefore(
                    "if (rgds.r3.SaveSlotTouch.update(this)) return;");
        } else if (simple.equals("RenamePopup") || simple.equals("SeedPanel")) {
            CtMethod open = simple.equals("RenamePopup") ? target.getDeclaredMethod("open") :
                    target.getDeclaredMethod("show", new CtClass[0]);
            open.insertAfter("rgds.r3.TextKeyboard.open(this);");
            target.getDeclaredMethod("update").insertBefore(
                    "if (rgds.r3.TextKeyboard.update(this)) return;");
            target.getDeclaredMethod("render").insertBefore(
                    "if (rgds.r3.TextKeyboard.owns(this)) return;");
            for (String name : simple.equals("RenamePopup") ?
                    new String[]{"confirm", "cancel"} : new String[]{"close"})
                target.getDeclaredMethod(name).insertAfter(
                        "if (!shown) rgds.r3.TextKeyboard.closed(this);");
        } else if (simple.equals("PotionPopUp")) {
            target.getDeclaredMethod("updateTargetMode").insertBefore(
                    "if (rgds.r3.UpperInteraction.guardTarget(this)) return;");
        } else if (SMALL_CONTROLS.contains(simple)) {
            target.getDeclaredMethod("update").insertAfter(
                    "rgds.r3.DualRender.nativeButtonRelease(this.hb);");
            target.getDeclaredMethod("render").insertBefore(
                    "rgds.r3.DualRender.smallControl($1,this," + simple.equals("MenuButton") + ");");
            target.getDeclaredMethod("render").insertAfter("rgds.r3.DualRender.pop($1);", true);
        } else if (simple.equals("InfiniteSpeechBubble") || simple.equals("SpeechTextEffect")) {
            target.getDeclaredMethod("render").insertBefore("rgds.r3.DualRender.narration($1);");
            target.getDeclaredMethod("render").insertAfter("rgds.r3.DualRender.pop($1);", true);
        } else if (simple.equals("DungeonMap")) {
            target.getDeclaredMethod("update").instrument(new ExprEditor() {
                public void edit(FieldAccess field) throws CannotCompileException {
                    if (field.isReader() && field.getClassName().endsWith(".InputHelper") &&
                            field.getFieldName().equals("justClickedLeft"))
                        field.replace("{ $_ = rgds.r3.MapTouch.bossClick($proceed()); }");
                }
            });
            for (String name : new String[]{"renderNormalMap", "renderFinalActMap"})
                target.getDeclaredMethod(name).instrument(new ExprEditor() {
                    public void edit(MethodCall c) throws CannotCompileException {
                        if (c.getClassName().endsWith(".Legend") && c.getMethodName().equals("render"))
                            route(c, 1, false);
                    }
                });
        } else if (simple.equals("DungeonMapScreen")) {
            target.getDeclaredMethod("update").insertBefore(
                    "rgds.r3.MapTouch.begin(this,scrollWaitTimer);");
            target.getDeclaredMethod("updateMouse").insertBefore(
                    "if (rgds.r3.MapTouch.controls()) return;");
            target.getDeclaredMethod("updateControllerInput").insertBefore(
                    "if (rgds.r3.MapTouch.controls()) return;");
            target.getDeclaredMethod("updateYOffset").insertBefore(
                    "if (rgds.r3.MapTouch.controls()) { grabbedScreen = false;"
                    + "targetOffsetY = rgds.r3.MapTouch.scroll(targetOffsetY); updateAnimation(); return; }");
            for (String method : new String[]{"open", "close", "closeInstantly"})
                target.getDeclaredMethod(method).insertBefore("rgds.r3.MapTouch.cancel();");
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getClassName().endsWith(".FontHelper") ||
                            c.getMethodName().equals("renderControllerUi")) route(c, 1, false);
                }
            });
        } else if (simple.equals("CreditsScreen") || simple.equals("LeaderboardScreen")) {
            // These native menu pages close on Escape, while B only exposes
            // the controller cancel action on the console input path.
            String close = simple.equals("CreditsScreen") ? "close()" : "hide()";
            target.getDeclaredMethod("update").insertBefore(
                    "if (com.megacrit.cardcrawl.helpers.controller.CInputActionSet.cancel.isJustPressed()) {"
                    + "com.megacrit.cardcrawl.helpers.controller.CInputActionSet.cancel.unpress();"
                    + close + "; return; }");
        } else if (simple.equals("MapCircleEffect")) {
            target.getDeclaredMethod("render").insertBefore("rgds.r3.DualRender.mapEffect($1);");
            target.getDeclaredMethod("render").insertAfter("rgds.r3.DualRender.endPage($1,true);", true);
        } else if (simple.equals("EventRoom")) {
            for (String method : new String[]{"render", "renderAboveTopPanel"})
                target.getDeclaredMethod(method).instrument(new ExprEditor() {
                    public void edit(MethodCall c) throws CannotCompileException {
                        if (c.getClassName().endsWith(".AbstractEvent"))
                            routeExpression(c, "rgds.r3.DualRender.eventTarget($0)");
                    }
                });
        } else if (simple.equals("TitleBackground")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getMethodName().equals("renderRegion")) {
                        c.replace("{ rgds.r3.DualRender.titleLayer($1,this,$2,$4);"
                                + "try { $proceed($$); } finally { rgds.r3.DualRender.endPage($1,true); } }");
                    } else if (c.getClassName().endsWith(".TitleCloud")) {
                        c.replace("{ rgds.r3.DualRender.push($1,0,false);"
                                + "if (rgds.r3.DualRender.midCloud(this,$0)) rgds.r3.DualRender.beginBackground($1);"
                                + "try { $proceed($$); } finally { rgds.r3.DualRender.endPage($1,true); } }");
                    } else if (c.getClassName().endsWith(".TitleDustEffect")) route(c, 1, false);
                }
            });
        } else if (simple.equals("MainMenuScreen")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getClassName().endsWith(".SpriteBatch") && c.getMethodName().equals("draw"))
                        c.replace("{ if ($1 == com.megacrit.cardcrawl.helpers.ImageMaster.WHITE_SQUARE_IMG) {"
                                + "rgds.r3.DualRender.beginBackground($0); try { $proceed($$); }"
                                + "finally { rgds.r3.DualRender.endBackground($0); }"
                                + "} else { $proceed($$); } }");
                }
            });
        } else if (simple.equals("CharacterOption")) {
            fixed(target.getDeclaredMethod("renderInfo"), 0);
        } else if (simple.equals("NeowNarrationScreen")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getClassName().endsWith(".SpeechWord") && c.getMethodName().equals("render"))
                        route(c, 0, false);
                }
            });
        } else if (simple.equals("NeowEvent")) {
            for (CtConstructor constructor : target.getDeclaredConstructors())
                constructor.insertAfter("rgds.r3.StartupWarmup.attachNeow(this);");
        } else if (simple.equals("CharacterSelectScreen")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    String method = c.getMethodName(), owner = c.getClassName();
                    if (method.equals("render") || method.equals("renderSeedSettings") ||
                            method.equals("renderAscensionMode")) route(c, 1, false);
                    else if (owner.endsWith(".SpriteBatch") && method.equals("draw")) mirrorDraw(c);
                }
            });
        } else if (simple.equals("CampfireUI")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getMethodName().equals("renderFire") ||
                            c.getClassName().endsWith(".AbstractPlayer")) route(c, 0, false);
                }
            });
        } else if (simple.equals("Merchant")) {
            for (CtConstructor constructor : target.getDeclaredConstructors())
                constructor.insertAfter("rgds.r3.StartupWarmup.attachMerchant(this);");
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    // Shop inventory stays on the lower panel, but the merchant
                    // character is an upper-panel scene actor.
                    if (c.getClassName().endsWith(".AnimatedNpc")) route(c, 0, false);
                }
            });
        } else if (simple.equals("ShopSpeechBubble") || simple.equals("SpeechTextEffect")) {
            // Shop dialogue is part of the merchant performance, not inventory.
            target.getDeclaredMethod("render").insertBefore("rgds.r3.DualRender.push($1,0,false);");
            target.getDeclaredMethod("render").insertAfter("rgds.r3.DualRender.pop($1);", true);
        } else if (simple.equals("GenericEventDialog") || simple.equals("RoomEventDialog")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    String owner = c.getClassName(), method = c.getMethodName();
                    if (owner.endsWith(".LargeDialogOptionButton") && method.equals("render"))
                        c.replace("{ rgds.r3.DualRender.eventOption($1,$0,this.optionList.size());"
                                + "try { $proceed($$); } finally { rgds.r3.DualRender.pop($1); } }");
                }
            });
        } else if (simple.equals("SingleCardViewPopup") || simple.equals("SingleRelicViewPopup")) {
            target.getDeclaredMethod("update").insertBefore(
                    "if (rgds.r3.DetailControls.update(this)) return;");
            target.getDeclaredMethod("updateInput").instrument(new ExprEditor() {
                public void edit(FieldAccess field) throws CannotCompileException {
                    if (field.isReader() && field.getClassName().endsWith(".InputHelper") &&
                            (field.getFieldName().equals("justClickedLeft") ||
                             field.getFieldName().equals("justReleasedClickLeft")))
                        field.replace("{ $_ = rgds.r3.DetailControls.outsideClick(this,$proceed(),"
                                + field.getFieldName().equals("justReleasedClickLeft") + "); }");
                }
            });
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    String method = c.getMethodName();
                    if (method.equals("renderArrows") || method.equals("renderBetaArtToggle") ||
                            method.equals("renderUpgradeViewToggle")) route(c, 1, false);
                    else if (c.getClassName().endsWith(".SpriteBatch") && method.equals("draw")) {
                        if (simple.equals("SingleCardViewPopup")) {
                            c.replace("{ if ($1 == com.megacrit.cardcrawl.helpers.ImageMaster.WHITE_SQUARE_IMG) {"
                                    + "rgds.r3.DualRender.beginBackground($0); try { $proceed($$); }"
                                    + "finally { rgds.r3.DualRender.endBackground($0); }"
                                    + "} else { rgds.r3.DualRender.push($0,1,false);"
                                    + "try { $proceed($$); } finally { rgds.r3.DualRender.pop($0); } } }");
                        } else mirrorDraw(c);
                    }
                }
            });
        } else if (java.util.Arrays.asList("DeathScreen", "VictoryScreen",
                "UnlockCharacterScreen", "NeowUnlockScreen").contains(simple)) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getMethodName().equals("render") && c.getClassName().contains(".ui.buttons."))
                        route(c, 1, false);
                    else if (c.getClassName().endsWith(".SpriteBatch") && c.getMethodName().equals("draw"))
                        mirrorDraw(c);
                }
            });
        } else if (simple.equals("StatsScreen") || simple.equals("RunHistoryScreen")) {
            String inner = simple.equals("StatsScreen") ? "renderStatScreen" : "renderRunHistoryScreen";
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getMethodName().equals(inner)) route(c, 1, false);
                }
            });
        } else if (simple.equals("CreditsScreen")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getClassName().endsWith(".SpriteBatch") &&
                            c.getMethodName().equals("draw")) {
                        c.replace("{ if ($1 != com.megacrit.cardcrawl.helpers.ImageMaster.WHITE_SQUARE_IMG) "
                                + "$proceed($$); }");
                    }
                }
            });
        } else if (simple.equals("PatchNotesScreen")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getClassName().endsWith(".FontHelper") && c.getMethodName().startsWith("render"))
                        mirrorCall(c, 1);
                }
            });
        }
        String id = ScreenRoutes.id(target.getName());
        if (simple.equals("CardGroup") || simple.equals("StoreRelic") || simple.equals("StorePotion") ||
                id != null && ScreenRoutes.previewPage(id) && ScreenRoutes.LOWER.containsKey(target.getName())) {
            for (CtMethod method : target.getDeclaredMethods()) {
                if (!method.getName().startsWith("render")) continue;
                method.instrument(new ExprEditor() {
                    public void edit(MethodCall c) throws CannotCompileException {
                        String owner = c.getClassName(), method = c.getMethodName();
                        if ((owner.endsWith(".AbstractCard") && (method.equals("render") ||
                                method.equals("renderInLibrary"))) ||
                                (owner.endsWith(".AbstractRelic") &&
                                        (method.equals("render") || method.equals("renderWithoutAmount"))) ||
                                (owner.endsWith(".AbstractPotion") &&
                                        (method.equals("labRender") || method.equals("shopRender"))))
                            c.replace("{ rgds.r3.DualRender.preview($1,$0,this);"
                                    + "try { $proceed($$); } finally {"
                                    + "rgds.r3.DualRender.endPage($1,true); } }");
                    }
                });
            }
        }
    }

    private static void mirrorCall(MethodCall call, int screen) throws CannotCompileException {
        call.replace("{ rgds.r3.DualRender.push($1," + screen + ",false);"
                + "rgds.r3.DualRender.beginBackground($1);"
                + "try { $proceed($$); } finally { rgds.r3.DualRender.endBackground($1);"
                + "rgds.r3.DualRender.pop($1); } }");
    }

    private static void mirrorDraw(MethodCall call) throws CannotCompileException {
        call.replace("{ rgds.r3.DualRender.beginBackground($0);"
                + "try { $proceed($$); } finally { rgds.r3.DualRender.endBackground($0); } }");
    }

    private static void fixed(CtMethod method, int screen) throws CannotCompileException {
        method.insertBefore("rgds.r3.DualRender.push($1," + screen + ",false);");
        method.insertAfter("rgds.r3.DualRender.pop($1);", true);
    }

    private static void routeExpression(MethodCall call, String screen) throws CannotCompileException {
        call.replace("{ rgds.r3.DualRender.push($1," + screen + ",false);"
                + "try { $proceed($$); } finally { rgds.r3.DualRender.pop($1); } }");
    }

    private static void info(CtMethod method, String kind) throws CannotCompileException {
        method.insertBefore("rgds.r3.DualRender.pushInfo($1,this,\"" + kind + "\");");
        method.insertAfter("rgds.r3.DualRender.pop($1);", true);
    }

    private static void route(MethodCall call, int screen, boolean hand) throws CannotCompileException {
        call.replace("{ rgds.r3.DualRender.push($1," + screen + "," + hand + ");"
                + "try { $proceed($$); } finally { rgds.r3.DualRender.pop($1); } }");
    }
}
