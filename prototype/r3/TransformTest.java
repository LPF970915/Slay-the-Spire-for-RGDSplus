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
        java.util.Set<String> inventory = new java.util.LinkedHashSet<String>(java.util.Arrays.asList(names));
        inventory.add("com/megacrit/cardcrawl/screens/charSelect/CharacterOption");
        inventory.add("com/megacrit/cardcrawl/rooms/EventRoom");
        inventory.add("com/megacrit/cardcrawl/scenes/TitleBackground");
        inventory.add("com/megacrit/cardcrawl/map/DungeonMap");
        inventory.add("com/megacrit/cardcrawl/vfx/MapCircleEffect");
        for (String control : rgds.r3.DualAgent.SMALL_CONTROLS) {
            String prefix = control.startsWith("Menu") ? "screens/mainMenu/" : "ui/buttons/";
            inventory.add("com/megacrit/cardcrawl/" + prefix + control);
        }
        ClassPool pool = new ClassPool(true);
        pool.insertClassPath(args[0]);
        checkStates(pool, "com.megacrit.cardcrawl.dungeons.AbstractDungeon$CurrentScreen",
                rgds.r3.ScreenRoutes.DUNGEON);
        checkStates(pool, "com.megacrit.cardcrawl.screens.mainMenu.MainMenuScreen$CurScreen",
                rgds.r3.ScreenRoutes.MENU);
        if (!rgds.r3.ScreenRoutes.dungeonId("CHOOSE_ONE", "MonsterRoom").equals("U16") ||
                !rgds.r3.ScreenRoutes.dungeonId("UNRECOGNIZED", "MonsterRoom").equals("U33") ||
                rgds.r3.ScreenRoutes.knownRoom("ModRoom"))
            throw new AssertionError("Choice/fallback policy");
        for (java.util.Map<String,String> routes : java.util.Arrays.asList(
                rgds.r3.ScreenRoutes.LOWER, rgds.r3.ScreenRoutes.MIRROR, rgds.r3.ScreenRoutes.UPPER))
            for (String name : routes.keySet()) inventory.add(name.replace('.', '/'));
        try (ZipFile game = new ZipFile(args[0])) {
            for (String name : inventory) {
                byte[] input = game.getInputStream(game.getEntry(name + ".class")).readAllBytes();
                byte[] output = transformer[0].transform(TransformTest.class.getClassLoader(),
                        name, null, null, input);
                if (output == null || java.util.Arrays.equals(input, output))
                    throw new AssertionError("No routing inserted for " + name);
                if (rgds.r3.ScreenRoutes.id(name.replace('/', '.')) != null) {
                    CtClass page = pool.makeClass(new ByteArrayInputStream(output));
                    final int[] enter = new int[1], exit = new int[1];
                    page.getDeclaredMethod("render").instrument(new ExprEditor() {
                        public void edit(MethodCall c) {
                            if (!c.getClassName().equals("rgds.r3.DualRender")) return;
                            if (c.getMethodName().equals("page")) enter[0]++;
                            if (c.getMethodName().equals("endPage")) exit[0]++;
                        }
                    });
                    page.detach();
                    if (enter[0] != 1 || exit[0] < 1)
                        throw new AssertionError("Page scope missing " + name);
                }
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
        System.out.println("Native class transformations passed: " + inventory.size());
    }

    private static void checkStates(ClassPool pool, String type, java.util.Map<String, String> policy)
            throws Exception {
        java.util.Set<String> actual = new java.util.TreeSet<String>();
        for (javassist.CtField field : pool.get(type).getDeclaredFields())
            if ((field.getModifiers() & javassist.bytecode.AccessFlag.ENUM) != 0)
                actual.add(field.getName());
        if (!actual.equals(policy.keySet())) throw new AssertionError("Uncovered state " + type);
        System.out.println("Native enum coverage passed: " + type + " " + actual.size());
    }
}
