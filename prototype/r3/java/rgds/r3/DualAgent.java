package rgds.r3;

import java.io.ByteArrayInputStream;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import javassist.*;
import javassist.expr.ExprEditor;
import javassist.expr.MethodCall;

/** Game-free method routing. The original game and stable adapter are not edited. */
public final class DualAgent {
    private static final String CORE = "com/megacrit/cardcrawl/";
    public static final java.util.Set<String> SMALL_CONTROLS = new java.util.LinkedHashSet<String>(
            java.util.Arrays.asList("MenuButton", "MenuCancelButton", "CancelButton", "ConfirmButton",
                    "GridSelectConfirmButton", "ReturnToMenuButton", "UnlockConfirmButton",
                    "CardSelectConfirmButton", "SkipCardButton"));

    public static void premain(String args, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            public byte[] transform(ClassLoader loader, String name, Class<?> cls,
                                    ProtectionDomain domain, byte[] bytes) {
                if (!name.startsWith(CORE) &&
                    !name.equals("com/badlogic/gdx/backends/lwjgl/LwjglApplicationConfiguration") &&
                    !name.equals("com/badlogic/gdx/graphics/g2d/SpriteBatch"))
                    return null;
                String simple = name.substring(name.lastIndexOf('/') + 1);
                boolean registered = ScreenRoutes.id(name.replace('/', '.')) != null;
                if (!registered && !SMALL_CONTROLS.contains(simple) && !java.util.Arrays.asList("CardCrawlGame", "AbstractDungeon", "AbstractPlayer",
                        "MainMenuScreen", "LwjglApplicationConfiguration", "OverlayMenu",
                        "AbstractMonster", "AbstractCreature", "Hitbox", "SpriteBatch",
                        "CharacterOption", "EventRoom", "TitleBackground", "DungeonMap",
                        "MapCircleEffect").contains(simple)) return null;
                CtClass target = null;
                try {
                    ClassPool pool = new ClassPool(true);
                    pool.insertClassPath(new LoaderClassPath(loader));
                    target = pool.makeClass(new ByteArrayInputStream(bytes));
                    if (simple.equals("SpriteBatch")) {
                        target.getDeclaredMethod("flush").instrument(new ExprEditor() {
                            public void edit(MethodCall c) throws CannotCompileException {
                                if (c.getClassName().equals("com.badlogic.gdx.graphics.Mesh") &&
                                        c.getMethodName().equals("render"))
                                    c.replace("{ $proceed($$); if (rgds.r3.DualRender.mirrorBatch()) {"
                                        + "rgds.r3.DualRender.lowerBackgroundViewport();"
                                        + "try { $proceed($$); } finally {"
                                        + "rgds.r3.DualRender.restoreBackgroundViewport(); } } }");
                            }
                        });
                    } else if (simple.equals("LwjglApplicationConfiguration")) {
                        target.makeClassInitializer().insertAfter("disableAudio = true;");
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
                                    mirrorCall(c, 0);
                                } else if (method.equals("render") &&
                                        (owner.endsWith(".OverlayMenu") ||
                                         owner.endsWith(".CancelButton"))) {
                                    route(c, 1, false);
                                }
                            }
                        });
                    } else if (simple.equals("Hitbox")) {
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
                    } else if (simple.equals("AbstractMonster")) {
                        for (String method : new String[]{"renderIntent", "renderDamageRange",
                                "renderIntentVfxBehind", "renderIntentVfxAfter"})
                            info(target.getDeclaredMethod(method), "intent");
                    } else if (simple.equals("AbstractPlayer")) {
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
        });
    }

    private static void pageRouting(CtClass target, String simple) throws Exception {
        if (SMALL_CONTROLS.contains(simple)) {
            target.getDeclaredMethod("render").insertBefore(
                    "rgds.r3.DualRender.smallControl($1,this," + simple.equals("MenuButton") + ");");
            target.getDeclaredMethod("render").insertAfter("rgds.r3.DualRender.pop($1);", true);
        } else if (simple.equals("DungeonMap")) {
            for (String name : new String[]{"renderNormalMap", "renderFinalActMap"})
                target.getDeclaredMethod(name).instrument(new ExprEditor() {
                    public void edit(MethodCall c) throws CannotCompileException {
                        if (c.getClassName().endsWith(".Legend") && c.getMethodName().equals("render"))
                            route(c, 1, false);
                    }
                });
        } else if (simple.equals("DungeonMapScreen")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    if (c.getClassName().endsWith(".FontHelper") ||
                            c.getMethodName().equals("renderControllerUi")) route(c, 1, false);
                }
            });
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
                        route(c, 1, false);
                }
            });
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
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    // Keep a native lower-screen entry at its existing hitbox.
                    if (c.getClassName().endsWith(".AnimatedNpc")) mirrorCall(c, 1);
                }
            });
        } else if (simple.equals("GenericEventDialog") || simple.equals("RoomEventDialog")) {
            target.getDeclaredMethod("render").instrument(new ExprEditor() {
                public void edit(MethodCall c) throws CannotCompileException {
                    String owner = c.getClassName(), method = c.getMethodName();
                    if (owner.endsWith(".LargeDialogOptionButton") && method.equals("render"))
                        route(c, 1, false);
                    else if (owner.endsWith(".SpriteBatch") && method.equals("draw")) mirrorDraw(c);
                }
            });
        } else if (simple.equals("SingleCardViewPopup") || simple.equals("SingleRelicViewPopup")) {
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
                    if (c.getMethodName().equals(inner)) mirrorCall(c, 1);
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
        if (id != null && ScreenRoutes.previewPage(id) && ScreenRoutes.LOWER.containsKey(target.getName())) {
            for (CtMethod method : target.getDeclaredMethods()) {
                if (!method.getName().startsWith("render")) continue;
                method.instrument(new ExprEditor() {
                    public void edit(MethodCall c) throws CannotCompileException {
                        String owner = c.getClassName(), method = c.getMethodName();
                        if ((owner.endsWith(".AbstractCard") && (method.equals("render") ||
                                method.equals("renderInLibrary"))) ||
                                (owner.endsWith(".AbstractRelic") && method.equals("render")) ||
                                (owner.endsWith(".AbstractPotion") && method.equals("labRender")))
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
