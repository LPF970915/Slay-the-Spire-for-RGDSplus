package rgds.r3;

import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.characters.AnimatedNpc;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.Texture;
import com.badlogic.gdx.files.FileHandle;
import java.util.ArrayList;

/**
 * Moves first-use class loading and agent transformation into the splash/menu
 * period. One class is initialized at a time so the game never blocks on a
 * large synchronous warmup batch.
 */
public final class StartupWarmup {
    private static final String[] CLASSES = {
        "com.megacrit.cardcrawl.screens.DungeonTransitionScreen",
        "com.megacrit.cardcrawl.neow.NeowEvent",
        "com.megacrit.cardcrawl.neow.NeowRoom",
        "com.megacrit.cardcrawl.cutscenes.NeowNarrationScreen",
        "com.megacrit.cardcrawl.events.RoomEventDialog",
        "com.megacrit.cardcrawl.events.GenericEventDialog",
        "com.megacrit.cardcrawl.screens.DungeonMapScreen",
        "com.megacrit.cardcrawl.map.DungeonMap",
        "com.megacrit.cardcrawl.shop.ShopScreen",
        "com.megacrit.cardcrawl.shop.Merchant",
        "com.megacrit.cardcrawl.shop.StoreRelic",
        "com.megacrit.cardcrawl.shop.StorePotion",
        "com.megacrit.cardcrawl.screens.CardRewardScreen",
        "com.megacrit.cardcrawl.screens.CombatRewardScreen",
        "com.megacrit.cardcrawl.screens.select.BossRelicSelectScreen",
        "com.megacrit.cardcrawl.rooms.MonsterRoom",
        "com.megacrit.cardcrawl.rooms.EventRoom",
        "com.megacrit.cardcrawl.core.OverlayMenu",
        "com.megacrit.cardcrawl.ui.buttons.ProceedButton",
        "com.megacrit.cardcrawl.cards.Soul",
        "com.megacrit.cardcrawl.vfx.InfiniteSpeechBubble",
        "com.megacrit.cardcrawl.vfx.SpeechTextEffect",
        "com.megacrit.cardcrawl.screens.DeathScreen",
        "com.megacrit.cardcrawl.screens.VictoryScreen",
        "com.megacrit.cardcrawl.vfx.MapCircleEffect",
        "com.megacrit.cardcrawl.vfx.GameDeckGlowEffect",
        "com.megacrit.cardcrawl.vfx.DiscardGlowEffect",
        "com.megacrit.cardcrawl.vfx.combat.DeckPoofParticle",
        "com.megacrit.cardcrawl.vfx.CardTrailEffect",
        "com.megacrit.cardcrawl.vfx.cardManip.CardGlowBorder",
        "com.megacrit.cardcrawl.vfx.cardManip.CardFlashVfx"
    };
    private static int next;
    private static int idleFrames;
    private static boolean complete;
    private static boolean stopped;
    private static String last;
    private static int assetStage;
    private static AnimatedNpc neowNpc;
    private static AnimatedNpc merchantNpc;
    private static int resourceStage;
    private static final ArrayList<Texture> residentTextures = new ArrayList<Texture>();
    private static final String[] RESOURCE_PATHS = {
        "images/npcs/rug/eng.png", "images/npcs/rug/zhs.png",
        "images/npcs/rug/zht.png", "images/npcs/rug/jpn.png",
        "images/npcs/rug/kor.png", "images/npcs/rug/rus.png",
        "images/npcs/purge/eng.png", "images/npcs/purge/zhs.png",
        "images/npcs/purge/zht.png", "images/npcs/purge/jpn.png",
        "images/npcs/sold_out/eng.png", "images/npcs/sold_out/zhs.png",
        "images/npcs/sold_out/zht.png", "images/npcs/sold_out/jpn.png",
        "images/ui/event/roomTextPanel.png", "images/ui/event/imgFrame.png",
        "images/ui/event/disabledButton.png", "images/ui/event/enabledButton.png",
        "images/ui/event/panel.png", "images/ui/dialog/largeCircle.png",
        "images/ui/dialog/largeCircle2.png", "images/ui/dialog/dialogDot.png",
        "images/ui/dialog/speechBubble2.png", "images/ui/dialog/speechBubble3.png",
        "images/ui/dialog/dialogPanel.png", "images/ui/dialog/smallCircle.png",
        "images/ui/topPanel/proceedButton.png", "images/ui/topPanel/proceedButtonOutline.png",
        "images/ui/topPanel/proceedButtonShadow.png", "images/ui/topPanel/cancelButton.png",
        "images/ui/topPanel/cancelButtonOutline.png", "images/ui/topPanel/cancelButtonShadow.png",
        "images/ui/charSelect/ironcladButton.png", "images/ui/charSelect/silentButton.png",
        "images/ui/charSelect/defectButton.png", "images/ui/charSelect/watcherButton.png"
    };

    private StartupWarmup() {}

    public static void tick() {
        if (complete || stopped || !menuPhase()) return;
        if (++idleFrames < 3) return;
        idleFrames = 0;
        if (next >= CLASSES.length) {
            warmAssets();
            return;
        }
        String name = CLASSES[next++];
        try {
            ClassLoader loader = Thread.currentThread().getContextClassLoader();
            Class.forName(name, true, loader == null ? StartupWarmup.class.getClassLoader() : loader);
            last = name;
            report("ready " + name + " " + next + "/" + CLASSES.length);
        } catch (Throwable error) {
            last = name + " failed";
            report("skip " + name + " " + error.getClass().getSimpleName());
        }
    }

    public static void stopForGameplay() {
        if (complete) stopped = true;
    }

    public static void attachNeow(Object owner) {
        if (neowNpc != null) replaceNpc(owner, "npc", neowNpc);
    }

    public static void attachMerchant(Object owner) {
        if (merchantNpc != null) replaceNpc(owner, "anim", merchantNpc);
    }

    public static String state() {
        if (complete) return "complete";
        if (stopped) return "stopped:" + next + "/" + CLASSES.length;
        return (last == null ? "pending" : last) + " " + next + "/" + CLASSES.length +
                " assets=" + assetStage + "/2 textures=" + resourceStage + "/" + RESOURCE_PATHS.length;
    }

    private static boolean menuPhase() {
        CardCrawlGame.GameMode mode = CardCrawlGame.mode;
        if (mode == CardCrawlGame.GameMode.SPLASH ||
                mode == CardCrawlGame.GameMode.CHAR_SELECT) return true;
        if (mode != CardCrawlGame.GameMode.GAMEPLAY || complete) return false;
        if (CardCrawlGame.dungeonTransitionScreen != null ||
                AbstractDungeon.currMapNode == null ||
                AbstractDungeon.currMapNode.room == null) return true;
        return AbstractDungeon.currMapNode.room.getClass().getSimpleName().equals("NeowRoom");
    }

    private static void report(String message) {
        if ("1".equals(System.getenv("RGDS_R3_PROFILE")))
            System.out.println("[r3-warmup] " + message);
    }

    private static void warmAssets() {
        if (assetStage == 0) {
            try {
                neowNpc = new AnimatedNpc(0, 0,
                        "images/npcs/neow/skeleton.atlas",
                        "images/npcs/neow/skeleton.json", "idle");
                assetStage = 1;
                report("asset-ready neow 1/2");
            } catch (Throwable error) {
                assetStage = 1;
                report("asset-skip neow " + error.getClass().getSimpleName());
            }
            return;
        }
        if (assetStage == 1) {
            try {
                merchantNpc = new AnimatedNpc(0, 0,
                        "images/npcs/merchant/skeleton.atlas",
                        "images/npcs/merchant/skeleton.json", "idle");
                assetStage = 2;
                report("asset-ready merchant 2/2");
            } catch (Throwable error) {
                assetStage = 2;
                report("asset-skip merchant " + error.getClass().getSimpleName());
            }
            return;
        }
        if (resourceStage < RESOURCE_PATHS.length) {
            String path = RESOURCE_PATHS[resourceStage++];
            try {
                FileHandle file = Gdx.files.internal(path);
                if (file.exists()) residentTextures.add(new Texture(file, false));
                report("resource-ready " + path + " " + resourceStage + "/" + RESOURCE_PATHS.length);
            } catch (Throwable error) {
                report("resource-skip " + path + " " + error.getClass().getSimpleName());
            }
            return;
        }
        complete = true;
        report("complete textures=" + residentTextures.size());
    }

    private static void replaceNpc(Object owner, String fieldName, AnimatedNpc replacement) {
        try {
            java.lang.reflect.Field field = owner.getClass().getDeclaredField(fieldName);
            field.setAccessible(true);
            Object previous = field.get(owner);
            if (previous instanceof AnimatedNpc && previous != replacement) {
                AnimatedNpc old = (AnimatedNpc)previous;
                if (old.skeleton != null && replacement.skeleton != null)
                    replacement.skeleton.setPosition(old.skeleton.getX(), old.skeleton.getY());
                old.dispose();
            }
            field.set(owner, replacement);
            if (fieldName.equals("npc")) neowNpc = null;
            if (fieldName.equals("anim")) merchantNpc = null;
        } catch (ReflectiveOperationException error) {
            throw new IllegalStateException("Unable to reuse warmed NPC", error);
        }
    }
}
