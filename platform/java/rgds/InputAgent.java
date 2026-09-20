package rgds;

import java.io.ByteArrayInputStream;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.security.ProtectionDomain;
import javassist.ClassPool;
import javassist.CtClass;
import javassist.CtMethod;
import javassist.CtNewMethod;
import javassist.LoaderClassPath;
import javassist.Modifier;
import javassist.CannotCompileException;
import javassist.expr.ExprEditor;
import javassist.expr.MethodCall;

/** Input and texture compatibility, with bounded diagnostics; no game assets. */
public final class InputAgent {
    private static long nextReport;
    private static int frames;
    private static int slowFrames;
    private static int updates;
    private static Field blockerInstance;
    private static Field blockerDelegate;

    public static void premain(String args, Instrumentation instrumentation) {
        instrumentation.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String name, Class<?> type,
                    ProtectionDomain domain, byte[] bytes) {
                if (!"com/megacrit/cardcrawl/core/CardCrawlGame".equals(name)
                        && !"com/megacrit/cardcrawl/helpers/input/InputHelper".equals(name)
                        && !"com/badlogic/gdx/backends/lwjgl/LwjglInput".equals(name)
                        && !"com/megacrit/cardcrawl/ui/panels/RenamePopup".equals(name)
                        && !"com/megacrit/cardcrawl/core/Settings".equals(name)
                        && !"com/texcompress/TextureCompressAgent".equals(name)
                        && !"spire/agent/KeyboardBlocker".equals(name)
                        && !"spire/agent/KeyboardToControllerBridge".equals(name)) {
                    return null;
                }
                CtClass target = null;
                try {
                    ClassPool pool = new ClassPool(true);
                    pool.insertClassPath(new LoaderClassPath(loader));
                    target = pool.makeClass(new ByteArrayInputStream(bytes));
                    if (name.endsWith("/TextureCompressAgent")) {
                        // TexCompress also loads from the bootstrap loader, which
                        // cannot resolve adapter helpers from the application loader.
                        pool.insertClassPath(new LoaderClassPath(InputAgent.class.getClassLoader()));
                        CtMethod normalize = CtNewMethod.copy(
                                pool.get("rgds.TextureInput").getDeclaredMethod("rgba"),
                                "rgdsRgba", target, null);
                        normalize.setModifiers(Modifier.PRIVATE | Modifier.STATIC);
                        target.addMethod(normalize);
                        CtMethod cacheSeed = CtNewMethod.copy(
                                pool.get("rgds.TextureInput").getDeclaredMethod("cacheSeed"),
                                "rgdsCacheSeed", target, null);
                        cacheSeed.setModifiers(Modifier.PRIVATE | Modifier.STATIC);
                        target.addMethod(cacheSeed);
                        target.getDeclaredMethod("ensureFormatDetected").insertAfter(
                            "if (rgbaFmt == 37821) rgbFmt = -1;");
                        target.getDeclaredMethod("tryCompressAndUpload").instrument(new ExprEditor() {
                            @Override
                            public void edit(MethodCall call) throws CannotCompileException {
                                if (!call.getClassName().equals("com.texcompress.NativeCompressor")) return;
                                if (call.getMethodName().equals("nHash")) {
                                    call.replace("{ $_ = $proceed($1, $2, $3,"
                                            + " rgdsCacheSeed($1, $2, $3, $4)); }");
                                } else if (call.getMethodName().equals("nCompress")) {
                                    call.replace("{ if ($5 == 37821 &&"
                                            + " (long)$3 * (long)$4 * 4L > $1.remaining())"
                                            + " throw new IllegalArgumentException(\"ASTC requires RGBA input\");"
                                            + " $proceed($$); }");
                                }
                            }
                        });
                        target.getDeclaredMethod("tryCompressAndUpload").insertBefore(
                            "if ($4 < 128 || $5 < 128) return false;"
                            + "if (!Boolean.getBoolean(\"texcompress.disable\")"
                            + " && $2 == 0 && ($7 == 6407 || $7 == 6408) && $8 == 5121"
                            + " && $9 instanceof java.nio.ByteBuffer) {"
                            + " java.nio.ByteBuffer rgba = rgdsRgba("
                            + "(java.nio.ByteBuffer)$9, $4, $5, $7);"
                            + " if (rgba == null) return false;"
                            + " $9 = rgba; $7 = 6408; $3 = 6408;"
                            + "}");
                    } else if (name.endsWith("/CardCrawlGame")) {
                        target.getDeclaredMethod("render").insertBefore(
                            "rgds.InputAgent.frame(com.badlogic.gdx.Gdx.graphics.getRawDeltaTime());");
                    } else if (name.endsWith("/Settings")) {
                        target.getDeclaredMethod("initializeDisplay").insertAfter(
                            "System.out.println(\"[rgds-layout] logical=\"+WIDTH+\"x\"+HEIGHT"
                            + "+\" gdx=\"+com.badlogic.gdx.Gdx.graphics.getWidth()+\"x\""
                            + "+com.badlogic.gdx.Gdx.graphics.getHeight()"
                            + "+\" fourByThree=\"+isFourByThree+\" letterbox=\"+isLetterbox"
                            + "+\" scale=\"+scale+\" xScale=\"+xScale+\" yScale=\"+yScale);");
                    } else if (name.endsWith("/LwjglInput")) {
                        target.getDeclaredMethod("setInputProcessor").insertBefore(
                            "$1 = (com.badlogic.gdx.InputProcessor)rgds.InputAgent.wrap($1);");
                    } else if (name.endsWith("/RenamePopup")) {
                        target.getDeclaredMethod("open").insertAfter(
                            "textField = rgds.InputAgent.profileName($1, $2 ? null : "
                            + "com.megacrit.cardcrawl.core.CardCrawlGame.saveSlotPref.getString("
                            + "com.megacrit.cardcrawl.helpers.SaveHelper.slotName(\"PROFILE_NAME\", $1), \"\"));"
                            + "System.out.println(\"[rgds-profile] open slot=\"+$1+\" new=\"+$2+\" name=\"+textField);");
                        target.getDeclaredMethod("confirm").insertAfter(
                            "if (!shown) System.out.println(\"[rgds-profile] confirmed slot=\"+slot+\" name=\"+textField);");
                        target.getDeclaredMethod("cancel").insertAfter(
                            "System.out.println(\"[rgds-profile] cancelled slot=\"+slot);");
                    } else if (name.endsWith("/KeyboardBlocker")) {
                        target.getDeclaredMethod("keyDown").insertBefore("rgds.InputEdges.down($1);");
                        target.getDeclaredMethod("keyUp").insertBefore("rgds.InputEdges.up($1);");
                    } else if (name.endsWith("/KeyboardToControllerBridge")) {
                        pool.importPackage("spire.agent");
                        pool.importPackage("com.badlogic.gdx.controllers");
                        // Reuse the upstream controller and state fields, but give
                        // navigation dedicated keys instead of sharing L2's A key.
                        target.getDeclaredMethod("updateFromKeyboard").setBody(
                            "{ VirtualController c = VirtualControllerInjector.getVirtualController();"
                            + "if (c == null) return;"
                            + "int[] keys = {62,131,52,66,45,33,41,61,29,46};"
                            + "int[] buttons = {0,1,2,3,4,5,6,7,1004,-1004};"
                            + "for (int i=0; i<keys.length; i++) {"
                            + " Integer key = Integer.valueOf(keys[i]);"
                            + " boolean down = rgds.InputEdges.pressed(keys[i]);"
                            + " Boolean old = (Boolean)previousKeyState.get(key);"
                            + " if (down != (old != null && old.booleanValue())) {"
                            + "  c.setButtonPressed(buttons[i], down);"
                            + "  previousKeyState.put(key, Boolean.valueOf(down));"
                            + " }"
                            + "}"
                            + "boolean l=rgds.InputEdges.pressed(21);"
                            + "boolean r=rgds.InputEdges.pressed(22);"
                            + "boolean u=rgds.InputEdges.pressed(19);"
                            + "boolean d=rgds.InputEdges.pressed(20);"
                            + "if (l!=leftPressed || r!=rightPressed || u!=upPressed || d!=downPressed) {"
                            + " leftPressed=l; rightPressed=r; upPressed=u; downPressed=d;"
                            + " float x=(r?1.0f:0.0f)-(l?1.0f:0.0f);"
                            + " float y=(d?1.0f:0.0f)-(u?1.0f:0.0f);"
                            + " c.setAxisValue(1,x); c.setAxisValue(0,y);"
                            + " PovDirection p=PovDirection.center;"
                            + " if(y<0) p=x<0?PovDirection.northWest:(x>0?PovDirection.northEast:PovDirection.north);"
                            + " else if(y>0) p=x<0?PovDirection.southWest:(x>0?PovDirection.southEast:PovDirection.south);"
                            + " else if(x<0) p=PovDirection.west; else if(x>0) p=PovDirection.east;"
                            + " c.setPovDirection(p);"
                            + " System.out.println(\"[rgds-input] direction=\"+p);"
                            + "}"
                            + "}");
                    } else {
                        target.getDeclaredMethod("updateFirst").insertBefore("rgds.InputAgent.update();");
                    }
                    System.out.println("[rgds-input] instrumented " + name);
                    return target.toBytecode();
                } catch (Exception error) {
                    error.printStackTrace();
                    return null;
                } finally {
                    if (target != null) target.detach();
                }
            }
        }, true);
    }

    // Screens replace InputProcessor when opening/closing text dialogs. Keep the
    // same keyboard state across that change, while forwarding pointer events
    // to the newly installed screen processor.
    public static synchronized Object wrap(Object delegate) {
        try {
            Class<?> type = Class.forName("spire.agent.KeyboardBlocker");
            if (blockerInstance == null) {
                blockerInstance = type.getDeclaredField("instance");
                blockerDelegate = type.getDeclaredField("originalProcessor");
                blockerInstance.setAccessible(true);
                blockerDelegate.setAccessible(true);
            }
            Object wrapper = blockerInstance.get(null);
            if (wrapper == null) {
                wrapper = type.getDeclaredConstructor().newInstance();
                blockerInstance.set(null, wrapper);
            }
            if (delegate != wrapper) {
                if (blockerDelegate.get(wrapper) != delegate) InputEdges.discardPending();
                blockerDelegate.set(wrapper, delegate);
                System.out.println("[rgds-input] processor="
                        + (delegate == null ? "none" : delegate.getClass().getName()));
            }
            return wrapper;
        } catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Unable to preserve gamepad input processor", error);
        }
    }

    public static String profileName(int slot, String existing) {
        return existing != null && !existing.trim().isEmpty()
                ? existing : "RGDS " + (slot + 1);
    }

    public static void update() {
        updates++;
    }

    public static void frame(float delta) {
        InputEdges.beginFrame();
        RuntimeProbe.sample();
        frames++;
        if (delta > 0.1f) slowFrames++;
        long now = System.nanoTime();
        if (now >= nextReport) {
            System.out.println("[rgds-input] frames=" + frames + " updates=" + updates
                    + " slow=" + slowFrames + " delta=" + delta);
            frames = slowFrames = updates = 0;
            nextReport = now + 5_000_000_000L;
        }
    }
}
