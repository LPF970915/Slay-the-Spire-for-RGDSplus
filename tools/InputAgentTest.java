import com.badlogic.gdx.InputProcessor;
import java.io.InputStream;
import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Proxy;
import java.nio.ByteBuffer;
import javassist.ClassPool;
import javassist.CtClass;
import java.io.ByteArrayInputStream;
import rgds.InputAgent;
import rgds.InputEdges;
import spire.agent.KeyboardBlocker;
import spire.agent.VirtualController;
import spire.agent.VirtualControllerInjector;

/** Uses game interfaces from the user's JAR, but never starts or packages it. */
public final class InputAgentTest {
    private static final class IsolatedLoader extends ClassLoader {
        IsolatedLoader() { super(ClassLoader.getPlatformClassLoader()); }
        Class<?> define(byte[] bytes) { return defineClass(null, bytes, 0, bytes.length); }
    }

    private static final class BridgeLoader extends ClassLoader {
        Class<?> define(byte[] bytes) { return defineClass(null, bytes, 0, bytes.length); }
    }

    private static void checkBridge(byte[] bytes) throws Exception {
        VirtualController controller = new VirtualController();
        java.lang.reflect.Field field = VirtualControllerInjector.class.getDeclaredField("virtualController");
        field.setAccessible(true);
        Object old = field.get(null);
        field.set(null, controller);
        try {
            java.lang.reflect.Method update = new BridgeLoader().define(bytes)
                    .getMethod("updateFromKeyboard");
            InputEdges.reset();
            for (int[] binding : new int[][]{{29, 1004}, {46, -1004}, {62, 0}, {131, 1}, {66, 3}}) {
                InputEdges.down(binding[0]);
                InputEdges.up(binding[0]);
                InputEdges.beginFrame();
                update.invoke(null);
                check(controller.getButton(binding[1]), "tap reaches action " + binding[1]);
                check(!controller.getButton(1003), "R2 must not trigger inspect-right");
                update.invoke(null);
                check(controller.getButton(binding[1]), "repeated update within frame");
                InputEdges.beginFrame();
                update.invoke(null);
                check(!controller.getButton(binding[1]), "action releases " + binding[1]);
            }
        } finally {
            field.set(null, old);
            InputEdges.reset();
        }
    }

    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    private static InputProcessor processor(int[] counters) {
        return (InputProcessor)Proxy.newProxyInstance(InputAgentTest.class.getClassLoader(),
                new Class<?>[]{InputProcessor.class}, (proxy, method, arguments) -> {
                    if (method.getName().equals("mouseMoved")) counters[0]++;
                    if (method.getName().equals("keyTyped")) counters[1]++;
                    return true;
                });
    }

    public static void main(String[] args) throws Exception {
        check(InputAgent.profileName(0, null).equals("RGDS 1"), "slot 1");
        check(InputAgent.profileName(1, "").equals("RGDS 2"), "slot 2");
        check(InputAgent.profileName(2, " ").equals("RGDS 3"), "slot 3");
        check(InputAgent.profileName(0, "My profile").equals("My profile"), "existing name");

        int[] first = new int[2], second = new int[2];
        InputProcessor wrapper = (InputProcessor)InputAgent.wrap(processor(first));
        wrapper.keyDown(62);
        check(KeyboardBlocker.isKeyPressed(62), "A pressed before dialog");
        check(InputAgent.wrap(processor(second)) == wrapper, "stable wrapper across dialog");
        check(KeyboardBlocker.isKeyPressed(62), "key state survives processor change");
        wrapper.keyUp(62);
        check(!KeyboardBlocker.isKeyPressed(62), "A release reaches wrapper inside dialog");
        wrapper.keyDown(131);
        check(KeyboardBlocker.isKeyPressed(131), "B works inside dialog");
        wrapper.keyUp(131);
        wrapper.keyDown(66);
        check(KeyboardBlocker.isKeyPressed(66), "Y works inside dialog");
        wrapper.keyUp(66);
        wrapper.keyTyped('x');
        check(second[1] == 0, "mapped X must not become profile text");
        wrapper.mouseMoved(1, 2);
        check(first[0] == 0 && second[0] == 1, "pointer targets new delegate");
        check(InputAgent.wrap(wrapper) == wrapper, "no recursive wrapping");
        InputAgent.wrap(processor(first));
        wrapper.mouseMoved(3, 4);
        check(first[0] == 1 && second[0] == 1, "pointer restored after dialog");
        InputAgent.wrap(null);
        check(!wrapper.mouseMoved(0, 0), "null delegate is safe");

        ClassFileTransformer[] transformer = new ClassFileTransformer[1];
        Instrumentation instrumentation = (Instrumentation)Proxy.newProxyInstance(
                InputAgentTest.class.getClassLoader(), new Class<?>[]{Instrumentation.class},
                (proxy, method, arguments) -> {
                    if (method.getName().equals("addTransformer"))
                        transformer[0] = (ClassFileTransformer)arguments[0];
                    return null;
                });
        InputAgent.premain("", instrumentation);
        for (String name : new String[]{"com/badlogic/gdx/backends/lwjgl/LwjglInput",
                "spire/agent/KeyboardBlocker", "spire/agent/KeyboardToControllerBridge",
                "com/megacrit/cardcrawl/core/Settings",
                "com/texcompress/TextureCompressAgent",
                "com/megacrit/cardcrawl/ui/panels/RenamePopup"}) {
            try (InputStream stream = InputAgentTest.class.getClassLoader()
                    .getResourceAsStream(name + ".class")) {
                check(stream != null, "user game class available");
                byte[] output = transformer[0].transform(InputAgentTest.class.getClassLoader(),
                        name, null, null, stream.readAllBytes());
                check(output != null, "transformation must compile: " + name);
                if (name.equals("spire/agent/KeyboardToControllerBridge"))
                    checkBridge(output);
                if (name.equals("com/texcompress/TextureCompressAgent")) {
                    CtClass probe = new ClassPool(true).makeClass(new ByteArrayInputStream(output));
                    // Skip hardware initialization; exercise the actual emitted helpers
                    // with no application/adapter classes visible to the target loader.
                    probe.removeConstructor(probe.getClassInitializer());
                    Class<?> isolated = new IsolatedLoader().define(probe.toBytecode());
                    probe.detach();
                    java.lang.reflect.Method normalize = isolated.getDeclaredMethod(
                            "rgdsRgba", ByteBuffer.class, int.class, int.class, int.class);
                    normalize.setAccessible(true);
                    ByteBuffer rgb = ByteBuffer.wrap(new byte[]{1, 2, 3});
                    ByteBuffer rgba = (ByteBuffer)normalize.invoke(null, rgb, 1, 1, 6407);
                    check(rgba.isDirect() && rgba.get(3) == (byte)255, "bootstrap-safe helper");
                    for (String field : new String[]{"rgbFmt", "rgbaFmt", "formatDetected"}) {
                        java.lang.reflect.Field f = isolated.getDeclaredField(field);
                        f.setAccessible(true);
                        if (field.equals("formatDetected")) f.setBoolean(null, true);
                        else f.setInt(null, 37821);
                    }
                    java.lang.reflect.Method detect = isolated.getDeclaredMethod("ensureFormatDetected");
                    detect.setAccessible(true);
                    detect.invoke(null);
                    java.lang.reflect.Field rgbFmt = isolated.getDeclaredField("rgbFmt");
                    rgbFmt.setAccessible(true);
                    check(rgbFmt.getInt(null) == -1, "opaque ASTC must not down-convert to RGB");
                }
            }
        }
        System.out.println("PASS: profile defaults, processor lifecycle, release, B/Y, text isolation, transforms");
    }
}
