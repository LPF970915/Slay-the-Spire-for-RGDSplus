import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Proxy;
import java.util.zip.ZipFile;
import java.io.ByteArrayInputStream;
import javassist.ClassPool;
import javassist.CtClass;
import javassist.expr.ExprEditor;
import javassist.expr.MethodCall;

public final class TransformTest {
    public static void main(String[] args) throws Exception {
        final ClassFileTransformer[] transformer = new ClassFileTransformer[1];
        Instrumentation fake = (Instrumentation)Proxy.newProxyInstance(
            TransformTest.class.getClassLoader(), new Class<?>[]{Instrumentation.class},
            (proxy, method, values) -> {
                if (method.getName().equals("addTransformer"))
                    transformer[0] = (ClassFileTransformer)values[0];
                return null;
            });
        rgds.r3.DualAgent.premain("", fake);
        String[] names = {
            "com/megacrit/cardcrawl/core/CardCrawlGame",
            "com/megacrit/cardcrawl/dungeons/AbstractDungeon",
            "com/megacrit/cardcrawl/characters/AbstractPlayer",
            "com/megacrit/cardcrawl/screens/mainMenu/MainMenuScreen",
            "com/megacrit/cardcrawl/core/OverlayMenu",
            "com/megacrit/cardcrawl/core/AbstractCreature",
            "com/megacrit/cardcrawl/monsters/AbstractMonster",
            "com/megacrit/cardcrawl/helpers/Hitbox",
            "com/badlogic/gdx/graphics/g2d/SpriteBatch",
            "com/badlogic/gdx/backends/lwjgl/LwjglApplicationConfiguration"
        };
        try (ZipFile game = new ZipFile(args[0])) {
            for (String name : names) {
                byte[] input = game.getInputStream(game.getEntry(name + ".class")).readAllBytes();
                byte[] output = transformer[0].transform(TransformTest.class.getClassLoader(),
                        name, null, null, input);
                if (output == null || java.util.Arrays.equals(input, output))
                    throw new AssertionError("No routing inserted for " + name);
                if (name.endsWith("/SpriteBatch")) {
                    CtClass batch = new ClassPool(true).makeClass(new ByteArrayInputStream(output));
                    final int[] calls = new int[1];
                    batch.getDeclaredMethod("flush").instrument(new ExprEditor() {
                        public void edit(MethodCall call) {
                            if (call.getClassName().equals("com.badlogic.gdx.graphics.Mesh") &&
                                    call.getMethodName().equals("render")) calls[0]++;
                        }
                    });
                    batch.detach();
                    if (calls[0] != 2) throw new AssertionError("Expected two GPU submissions");
                }
            }
        }
        System.out.println("R3 ten native class transformations passed");
    }
}
