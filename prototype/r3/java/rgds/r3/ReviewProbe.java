package rgds.r3;

import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.rooms.*;
import com.megacrit.cardcrawl.monsters.MonsterGroup;
import com.megacrit.cardcrawl.monsters.exordium.LouseNormal;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.helpers.*;
import com.megacrit.cardcrawl.screens.mainMenu.MainMenuScreen;
import com.megacrit.cardcrawl.screens.mainMenu.MenuPanelScreen.PanelScreen;
import java.nio.file.Path;
import java.util.ArrayList;

/** Native UI specimens in a disposable save clone, never gameplay acceptance. */
public final class ReviewProbe {
    public static final boolean enabled = "1".equals(System.getenv("RGDS_R4_REVIEW")) &&
            Path.of("").toAbsolutePath().normalize().getFileName().toString().equals("SlayTheSpireDualR4Review");
    private static MapRoomNode baseline;
    private static float playerX, playerY;
    private static final ArrayList<AbstractCard> baselineHand = new ArrayList<>();
    private static String scene = "";
    private static long nextFlash;

    public static String scene() { return enabled ? scene : ""; }

    private static void set(Object owner, String name, Object value) {
        Class<?> type = owner instanceof Class ? (Class<?>)owner : owner.getClass();
        for (; type != null; type = type.getSuperclass()) {
            try {
                java.lang.reflect.Field f = type.getDeclaredField(name);
                f.setAccessible(true);
                f.set(owner instanceof Class ? null : owner, value);
                return;
            } catch (NoSuchFieldException missing) {
                // Fixed, compiled field names only; no user-provided reflection.
            } catch (ReflectiveOperationException error) { throw new IllegalStateException(error); }
        }
        throw new IllegalArgumentException(name);
    }

    private static ArrayList<AbstractCard> cards() {
        ArrayList<AbstractCard> cards = new ArrayList<AbstractCard>();
        for (String id : new String[]{"Anger", "Shrug It Off", "Iron Wave"})
            cards.add(CardLibrary.getCard(id).makeCopy());
        return cards;
    }

    private static void room(AbstractRoom room, AbstractDungeon.RenderScene render) {
        MapRoomNode node = new MapRoomNode(baseline.x, baseline.y);
        node.room = room;
        // Native room transitions dispose the previous room, which this fixture reuses.
        AbstractDungeon.currMapNode = node;
        AbstractDungeon.rs = render;
        AbstractDungeon.scene.nextRoom(room);
        AbstractDungeon.player.hand.group.clear();
        set(AbstractDungeon.player, "hoveredCard", null);
        AbstractDungeon.overlayMenu.hideCombatPanels();
    }

    public static void open(String id) {
        if (!enabled || !id.matches("u(0[1-9]|[12][0-9]|3[0-3])"))
            throw new IllegalArgumentException("Review scenes require isolated review directory");
        if (baseline == null) {
            if (CardCrawlGame.mode != CardCrawlGame.GameMode.GAMEPLAY ||
                    AbstractDungeon.player == null || AbstractDungeon.isScreenUp)
                throw new IllegalStateException("Resume the cloned battle before the first specimen");
            baseline = AbstractDungeon.getCurrMapNode();
            playerX = AbstractDungeon.player.drawX; playerY = AbstractDungeon.player.drawY;
            baselineHand.addAll(AbstractDungeon.player.hand.group);
            if (baselineHand.isEmpty()) {
                // The disposable baseline can resume at a campfire or map with
                // no live hand; keep selection-page specimens actionable.
                baselineHand.addAll(cards());
            }
            if (baseline.room == null || baseline.room.monsters == null ||
                    baseline.room.monsters.monsters.isEmpty()) {
                MonsterRoom specimen = new MonsterRoom();
                MonsterGroup group = new MonsterGroup(new LouseNormal(420.0f, 0.0f));
                // setMonster stores the group but does not roll the first move.
                group.init();
                specimen.setMonster(group);
                baseline.room = specimen;
                AbstractDungeon.currMapNode = baseline;
                AbstractDungeon.scene.nextRoom(specimen);
                specimen.onPlayerEntry();
            }
        }
        scene = "";
        CardCrawlGame.cardPopup.close();
        CardCrawlGame.relicPopup.close();
        CardCrawlGame.dungeonTransitionScreen = null;
        AbstractDungeon.topPanel.potionUi.close();
        AbstractDungeon.isScreenUp = false;
        AbstractDungeon.screen = AbstractDungeon.CurrentScreen.NONE;
        AbstractDungeon.previousScreen = null;
        AbstractDungeon.currMapNode = baseline;
        AbstractDungeon.rs = AbstractDungeon.RenderScene.NORMAL;
        AbstractDungeon.scene.nextRoom(baseline.room);
        AbstractDungeon.topPanel.unhoverHitboxes();
        AbstractDungeon.overlayMenu.hideBlackScreen();
        ((com.badlogic.gdx.graphics.Color)DualRender.get(
                AbstractDungeon.overlayMenu, "blackScreenColor")).a = 0;
        AbstractDungeon.overlayMenu.cancelButton.hide();
        AbstractDungeon.overlayMenu.proceedButton.hide();
        AbstractDungeon.overlayMenu.showCombatPanels();
        AbstractDungeon.dynamicBanner.hide();
        AbstractDungeon.isFadingIn = false;
        AbstractDungeon.isFadingOut = false;
        AbstractDungeon.waitingOnFadeOut = false;
        AbstractDungeon.player.drawX = playerX; AbstractDungeon.player.drawY = playerY;
        AbstractDungeon.player.hand.group.clear();
        AbstractDungeon.player.hand.group.addAll(baselineHand);
        AbstractDungeon.player.hand.refreshHandLayout();
        set(AbstractDungeon.player, "inSingleTargetMode", false);
        set(AbstractDungeon.player, "isDraggingCard", false);
        set(AbstractDungeon.player, "hoveredMonster", null);
        AbstractDungeon.topLevelEffects.clear();
        AbstractDungeon.topLevelEffectsQueue.clear();
        AbstractDungeon.effectList.clear();
        AbstractDungeon.effectsQueue.clear();
        AbstractDungeon.fadeColor.a = 0;
        CardCrawlGame.mode = CardCrawlGame.GameMode.GAMEPLAY;
        MainMenuScreen menu = CardCrawlGame.mainMenuScreen;
        menu.fadedOut = false;
        menu.isFadingOut = false;
        menu.screenColor.a = 0;
        ((com.badlogic.gdx.graphics.Color)DualRender.get(menu, "overlayColor")).a = 0;
        set(menu, "superDarken", false);
        menu.isSettingsUp = false;
        menu.abandonPopup.hide();
        menu.saveSlotScreen.shown = false;
        menu.screen = MainMenuScreen.CurScreen.MAIN_MENU;
        menu.lighten();
        boolean menuScene = java.util.Arrays.asList("u02", "u03", "u04", "u05", "u27",
                "u29", "u30", "u31", "u32").contains(id);
        if (menuScene) {
            CardCrawlGame.mode = CardCrawlGame.GameMode.CHAR_SELECT;
            if (!id.equals("u02") && !id.equals("u27")) {
                menu.hideMenuButtons();
                menu.darken();
                menu.panelScreen.open(PanelScreen.COMPENDIUM);
            }
        }
        switch (id) {
            case "u01":
                CardCrawlGame.dungeonTransitionScreen =
                        new com.megacrit.cardcrawl.screens.DungeonTransitionScreen("TheCity");
                CardCrawlGame.dungeonTransitionScreen.isComplete = false;
                set(CardCrawlGame.dungeonTransitionScreen, "popup", null);
                break;
            case "u02": break;
            case "u03":
                menu.screen = MainMenuScreen.CurScreen.SAVE_SLOT;
                menu.saveSlotScreen.open("RGDS");
                break;
            case "u04": menu.charSelectScreen.open(false); break;
            case "u05": menu.customModeScreen.open(); break;
            case "u06":
                room(new com.megacrit.cardcrawl.neow.NeowRoom(false), AbstractDungeon.RenderScene.EVENT);
                AbstractDungeon.getCurrRoom().onPlayerEntry();
                break;
            case "u07": AbstractDungeon.dungeonMapScreen.open(false); break;
            case "u08": break;
            case "u09":
                set(AbstractDungeon.player, "hoveredCard", AbstractDungeon.player.hand.group.get(1));
                set(AbstractDungeon.player, "hoveredMonster", baseline.room.monsters.monsters.get(0));
                set(AbstractDungeon.player, "inSingleTargetMode", true);
                break;
            case "u10":
                AbstractDungeon.effectList.add(new com.megacrit.cardcrawl.vfx.combat.FlashAtkImgEffect(
                        baseline.room.monsters.monsters.get(0).hb.cX,
                        baseline.room.monsters.monsters.get(0).hb.cY,
                        com.megacrit.cardcrawl.actions.AbstractGameAction.AttackEffect.SLASH_DIAGONAL));
                break;
            case "u11": break;
            case "u12":
                AbstractDungeon.player.obtainPotion(new com.megacrit.cardcrawl.potions.FirePotion());
                AbstractDungeon.topPanel.potionUi.open(0, AbstractDungeon.player.potions.get(0));
                break;
            case "u13": AbstractDungeon.deckViewScreen.open(); break;
            case "u14": AbstractDungeon.handCardSelectScreen.open(
                    com.megacrit.cardcrawl.screens.select.HandCardSelectScreen.TEXT[0], 1, true); break;
            case "u15":
                AbstractDungeon.gridSelectScreen.open(AbstractDungeon.player.masterDeck.getUpgradableCards(),
                        1, com.megacrit.cardcrawl.screens.select.GridCardSelectScreen.TEXT[0], true, false, false, false);
                break;
            case "u16": AbstractDungeon.cardRewardScreen.chooseOneOpen(cards()); break;
            case "u17":
                baseline.room.rewards.clear();
                baseline.room.rewards.add(new com.megacrit.cardcrawl.rewards.RewardItem(25));
                baseline.room.rewards.add(new com.megacrit.cardcrawl.rewards.RewardItem(
                        new com.megacrit.cardcrawl.potions.FirePotion()));
                baseline.room.rewards.add(new com.megacrit.cardcrawl.rewards.RewardItem());
                AbstractDungeon.combatRewardScreen.open();
                break;
            case "u18":
                AbstractDungeon.cardRewardScreen.open(cards(), new com.megacrit.cardcrawl.rewards.RewardItem(),
                        com.megacrit.cardcrawl.screens.CardRewardScreen.TEXT[0]); break;
            case "u19":
                room(new TreasureRoomBoss(), AbstractDungeon.RenderScene.NORMAL);
                ((TreasureRoomBoss)AbstractDungeon.getCurrRoom()).chest =
                        new com.megacrit.cardcrawl.rewards.chests.BossChest();
                ArrayList<com.megacrit.cardcrawl.relics.AbstractRelic> relics = new ArrayList<>();
                for (String relic : new String[]{"Black Blood", "Cursed Key", "Sozu"})
                    relics.add(RelicLibrary.getRelic(relic).makeCopy());
                AbstractDungeon.bossRelicScreen.open(relics); break;
            case "u20":
                room(new ShopRoom(), AbstractDungeon.RenderScene.NORMAL);
                AbstractDungeon.getCurrRoom().onPlayerEntry();
                AbstractDungeon.shopScreen.open(); break;
            case "u21":
                room(new EventRoom(), AbstractDungeon.RenderScene.EVENT);
                AbstractDungeon.getCurrRoom().event = new com.megacrit.cardcrawl.events.exordium.BigFish();
                AbstractDungeon.getCurrRoom().event.onEnterRoom(); break;
            case "u22":
                room(new RestRoom(), AbstractDungeon.RenderScene.CAMPFIRE);
                AbstractDungeon.getCurrRoom().onPlayerEntry(); break;
            case "u23":
                room(new TreasureRoom(), AbstractDungeon.RenderScene.NORMAL);
                ((TreasureRoom)AbstractDungeon.getCurrRoom()).chest =
                        new com.megacrit.cardcrawl.rewards.chests.SmallChest(); break;
            case "u24": break;
            case "u25": CardCrawlGame.cardPopup.open(AbstractDungeon.player.masterDeck.group.get(0)); break;
            case "u26": AbstractDungeon.settingsScreen.open(); break;
            case "u27":
                menu.screen = MainMenuScreen.CurScreen.ABANDON_CONFIRM;
                menu.abandonPopup.show(); break;
            case "u28":
                AbstractDungeon.deathScreen = new com.megacrit.cardcrawl.screens.DeathScreen(baseline.room.monsters);
                AbstractDungeon.screen = AbstractDungeon.CurrentScreen.DEATH;
                AbstractDungeon.isScreenUp = true; break;
            case "u29": menu.cardLibraryScreen.open(); break;
            case "u30": menu.statsScreen.open(); break;
            case "u31": menu.creditsScreen.open(false); break;
            case "u32": menu.leaderboardsScreen.open(); break;
            case "u33": room(new EmptyRoom(), AbstractDungeon.RenderScene.NORMAL); break;
            default: throw new IllegalArgumentException(id);
        }
        scene = id;
    }

    @SuppressWarnings("unchecked")
    public static void tick() {
        if (!enabled) return;
        if (scene.equals("u01") && CardCrawlGame.dungeonTransitionScreen != null) {
            CardCrawlGame.dungeonTransitionScreen.timer = 1.8f;
            CardCrawlGame.dungeonTransitionScreen.isComplete = false;
        }
        if (scene.equals("u10") && System.nanoTime() > nextFlash) {
            AbstractDungeon.effectList.add(new com.megacrit.cardcrawl.vfx.combat.FlashAtkImgEffect(
                    baseline.room.monsters.monsters.get(0).hb.cX,
                    baseline.room.monsters.monsters.get(0).hb.cY,
                    com.megacrit.cardcrawl.actions.AbstractGameAction.AttackEffect.SLASH_DIAGONAL));
            nextFlash = System.nanoTime() + 220_000_000L;
        }
        if (scene.equals("u11")) {
            com.megacrit.cardcrawl.monsters.AbstractMonster monster = baseline.room.monsters.monsters.get(0);
            monster.hb.hovered = true;
            monster.intentHb.hovered = true;
            ArrayList<PowerTip> tips = new ArrayList<>();
            PowerTip intent = (PowerTip)DualRender.get(monster, "intentTip");
            if (intent != null && intent.header != null) tips.add(intent);
            if (!tips.isEmpty()) TipHelper.queuePowerTips(550, 650, tips);
        }
        if (scene.equals("u24") && !AbstractDungeon.player.relics.isEmpty()) {
            com.megacrit.cardcrawl.relics.AbstractRelic relic = AbstractDungeon.player.relics.get(0);
            TipHelper.queuePowerTips(160, 610, relic.tips);
        }
    }
}
