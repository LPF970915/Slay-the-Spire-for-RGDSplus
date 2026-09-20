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

    public static void premain(String args, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            public byte[] transform(ClassLoader loader, String name, Class<?> cls,
                                    ProtectionDomain domain, byte[] bytes) {
                if (!name.startsWith(CORE) &&
                    !name.equals("com/badlogic/gdx/backends/lwjgl/LwjglApplicationConfiguration"))
                    return null;
                String simple = name.substring(name.lastIndexOf('/') + 1);
                if (!java.util.Arrays.asList("CardCrawlGame", "AbstractDungeon", "AbstractPlayer",
                        "MainMenuScreen", "LwjglApplicationConfiguration").contains(simple)) return null;
                CtClass target = null;
                try {
                    ClassPool pool = new ClassPool(true);
                    pool.insertClassPath(new LoaderClassPath(loader));
                    target = pool.makeClass(new ByteArrayInputStream(bytes));
                    if (simple.equals("LwjglApplicationConfiguration")) {
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
                                else if (method.equals("render") &&
                                    (owner.endsWith("SingleCardViewPopup")
                                     || owner.endsWith("SingleRelicViewPopup")))
                                    route(c, 1, false);
                            }
                        });
                        target.getDeclaredMethod("update").insertBefore("rgds.r3.DualRender.logicTick();");
                    } else if (simple.equals("AbstractDungeon")) {
                        target.getDeclaredMethod("render").instrument(new ExprEditor() {
                            public void edit(MethodCall c) throws CannotCompileException {
                                String owner = c.getClassName(), method = c.getMethodName();
                                if (method.equals("renderCombatRoomFg")) {
                                    route(c, 1, false);
                                } else if (method.equals("renderBlackScreen")) {
                                    c.replace("{ $proceed($$); rgds.r3.DualRender.push($1, 1, false);"
                                            + "$proceed($$); rgds.r3.DualRender.pop($1); }");
                                } else if (method.equals("render") &&
                                        (owner.endsWith(".OverlayMenu") || owner.contains(".screens.")
                                         || owner.endsWith(".ShopScreen") || owner.endsWith(".FtueTip")
                                         || owner.endsWith(".CancelButton"))) {
                                    route(c, 1, false);
                                }
                            }
                        });
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

    private static void route(MethodCall call, int screen, boolean hand) throws CannotCompileException {
        call.replace("{ rgds.r3.DualRender.push($1," + screen + "," + hand + ");"
                + "try { $proceed($$); } finally { rgds.r3.DualRender.pop($1); } }");
    }
}
