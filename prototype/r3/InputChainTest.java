import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipFile;
import java.io.ByteArrayInputStream;
import javassist.ClassPool;
import javassist.CtClass;
import javassist.expr.ExprEditor;
import javassist.expr.MethodCall;

/** Exercise the actual upstream/stable/dual transformer ordering, not just raw game classes. */
public final class InputChainTest {
    public static void main(String[] args) throws Exception {
        List<ClassFileTransformer> early = new ArrayList<>(), late = new ArrayList<>();
        Instrumentation fake = (Instrumentation)Proxy.newProxyInstance(
            InputChainTest.class.getClassLoader(), new Class<?>[]{Instrumentation.class},
            (proxy, method, values) -> {
                if (method.getName().equals("addTransformer")) {
                    boolean retransforms = values.length > 1 && Boolean.TRUE.equals(values[1]);
                    (retransforms ? late : early).add((ClassFileTransformer)values[0]);
                }
                return null;
            });
        spire.agent.ControllerInjectionAgent.premain("", fake);
        rgds.InputAgent.premain("", fake);
        rgds.r3.DualAgent.premain("", fake);
        early.addAll(late);
        try (ZipFile game = new ZipFile(args[0])) {
            String[][] checks = {
                {"com/megacrit/cardcrawl/ui/panels/RenamePopup", "open", "rgds.r3.TextKeyboard"},
                {"com/megacrit/cardcrawl/screens/mainMenu/SaveSlot", "update", "rgds.r3.SaveSlotTouch"},
                {"com/megacrit/cardcrawl/ui/panels/SeedPanel", "show", "rgds.r3.TextKeyboard"},
                {"com/megacrit/cardcrawl/ui/panels/SeedPanel", "update", "rgds.r3.TextKeyboard"},
                {"com/megacrit/cardcrawl/ui/MultiPageFtue", "render", "rgds.r3.DualRender"},
                {"com/megacrit/cardcrawl/ui/MultiPageFtue", "update", "rgds.r3.TutorialTouch"},
                {"com/megacrit/cardcrawl/ui/buttons/ProceedButton", "update", "rgds.r3.TutorialTouch"},
                {"com/megacrit/cardcrawl/events/GenericEventDialog", "render", "rgds.r3.DualRender"},
                {"com/megacrit/cardcrawl/events/RoomEventDialog", "render", "rgds.r3.DualRender"},
                {"com/megacrit/cardcrawl/ui/panels/PotionPopUp", "updateTargetMode", "rgds.r3.UpperInteraction"},
                {"com/megacrit/cardcrawl/screens/SingleCardViewPopup", "updateInput", "rgds.r3.DetailControls"},
                {"com/megacrit/cardcrawl/screens/SingleRelicViewPopup", "updateInput", "rgds.r3.DetailControls"},
                {"com/megacrit/cardcrawl/screens/DungeonMapScreen", "update", "rgds.r3.MapTouch"},
                {"com/megacrit/cardcrawl/screens/DungeonMapScreen", "updateYOffset", "rgds.r3.MapTouch"},
                {"com/megacrit/cardcrawl/map/DungeonMap", "update", "rgds.r3.MapTouch"},
                {"com/megacrit/cardcrawl/helpers/input/InputHelper", "updateFirst", "rgds.r3.TouchInput"},
                {"com/badlogic/gdx/backends/lwjgl/LwjglInput", "getX", "rgds.r3.TouchInput"},
                {"com/megacrit/cardcrawl/core/AbstractCreature", "renderReticle", "rgds.r3.CombatEffects"},
                {"com/megacrit/cardcrawl/characters/AbstractPlayer", "useCard", "rgds.r3.CardFlight"},
                {"com/megacrit/cardcrawl/characters/AbstractPlayer", "updateControllerInput", "rgds.r3.CombatTouch"},
                {"com/megacrit/cardcrawl/cards/AbstractCard", "render", "rgds.r3.CardFlight"},
                {"com/megacrit/cardcrawl/cards/AbstractCard", "isHoveredInHand", "rgds.r3.DualRender"},
                {"com/megacrit/cardcrawl/cards/Soul", "update", "rgds.r3.CombatEffects"},
                {"com/megacrit/cardcrawl/core/GameCursor", "render", "rgds.r3.CombatEffects"},
                {"com/megacrit/cardcrawl/vfx/CardTrailEffect", "render", "rgds.r3.CombatEffects"},
                {"com/megacrit/cardcrawl/vfx/RefreshEnergyEffect", "render", "rgds.r3.CombatEffects"}
            };
            for (String[] check : checks) {
                String name = check[0];
                byte[] bytes = game.getInputStream(game.getEntry(name + ".class")).readAllBytes();
                for (ClassFileTransformer transformer : early) {
                    byte[] next = transformer.transform(InputChainTest.class.getClassLoader(),
                            name, null, null, bytes);
                    if (next != null) bytes = next;
                }
                CtClass transformed = new ClassPool(true).makeClass(new ByteArrayInputStream(bytes));
                final int[] touch = new int[1], stable = new int[1];
                for (javassist.CtMethod method : transformed.getDeclaredMethods()) {
                    if (!method.getName().equals(check[1])) continue;
                    method.instrument(new ExprEditor() {
                        public void edit(MethodCall call) {
                            if (call.getClassName().equals(check[2])) touch[0]++;
                            if (call.getClassName().equals("rgds.InputAgent")) stable[0]++;
                        }
                    });
                }
                if (touch[0] == 0 || name.endsWith("InputHelper") && stable[0] == 0)
                    throw new AssertionError("Hook lost in actual transformer chain: " + name);
                transformed.detach();
            }
        }
        System.out.println("Actual controller/stable/dual input and combat visual hooks preserved");
    }
}
