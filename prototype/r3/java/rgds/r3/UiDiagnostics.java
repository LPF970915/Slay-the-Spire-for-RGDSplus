package rgds.r3;

import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.Hitbox;
import com.megacrit.cardcrawl.potions.AbstractPotion;
import java.util.Properties;

/** Bounded passive UI snapshots for isolated interaction checks, not acceptance. */
public final class UiDiagnostics {
    private static void field(Properties out, String key, Object owner, String name) {
        Object value = DualRender.get(owner, name);
        if (value instanceof Boolean || value instanceof Number || value instanceof String || value instanceof Enum)
            out.setProperty(key, String.valueOf(value));
    }

    private static void hit(Properties out, String key, Object owner) {
        Object value = owner instanceof Hitbox ? owner : DualRender.get(owner, "hb");
        if (!(value instanceof Hitbox)) return;
        Hitbox hb = (Hitbox)value;
        DualRender.touchPosition(out, "ui." + key, hb);
        out.setProperty("ui." + key + ".hovered", Boolean.toString(hb.hovered));
    }

    private static void items(Properties out, String key, Object items) {
        if (!(items instanceof Iterable)) return;
        int i = 0;
        for (Object value : (Iterable<?>)items) {
            if (i >= 64) break;
            hit(out, key + "." + i, value);
            field(out, "ui." + key + "." + i + ".name", value, "name");
            field(out, "ui." + key + "." + i + ".text", value, "text");
            field(out, "ui." + key + "." + i + ".msg", value, "msg");
            field(out, "ui." + key + "." + i + ".disabled", value, "isDisabled");
            i++;
        }
        out.setProperty("ui." + key + ".count", Integer.toString(i));
    }

    public static void collect(Properties out) {
        try { collectAvailable(out); }
        catch (RuntimeException error) {
            // Optional telemetry must never interrupt a load/transition.
            out.setProperty("ui.diagnosticsError", error.toString());
        }
    }

    private static void collectAvailable(Properties out) {
        out.setProperty("ui.nativeTouch", Boolean.toString(Settings.isTouchScreen));
        out.setProperty("ui.controller", Boolean.toString(Settings.isControllerMode));
        out.setProperty("ui.cardPopup", Boolean.toString(CardCrawlGame.cardPopup.isOpen));
        out.setProperty("ui.relicPopup", Boolean.toString(CardCrawlGame.relicPopup.isOpen));
        out.setProperty("ui.seed", com.megacrit.cardcrawl.helpers.SeedHelper.getUserFacingSeedString());
        Object menu = CardCrawlGame.mainMenuScreen;
        Object slots = DualRender.get(menu, "saveSlotScreen");
        items(out, "slots", DualRender.get(slots, "slots"));
        field(out, "ui.savePopup", slots, "curPop");
        Object slotList = DualRender.get(slots, "slots");
        if (slotList instanceof java.util.List) {
            int n = 0;
            for (Object slot : (java.util.List<?>)slotList) {
                hit(out, "rename." + n, DualRender.get(slot, "renameHb"));
                hit(out, "delete." + n, DualRender.get(slot, "deleteHb"));
                hit(out, "slot." + n, DualRender.get(slot, "slotHb"));
                field(out, "ui.slot." + n + ".name", slot, "name");
                field(out, "ui.slot." + n + ".empty", slot, "emptySlot");
                n++;
            }
        }
        hit(out, "seed", DualRender.get(DualRender.get(menu, "charSelectScreen"), "seedHb"));
        hit(out, "customSeed", DualRender.get(DualRender.get(menu, "customModeScreen"), "seedHb"));
        DetailControls.diagnostics(out);
        if (CardCrawlGame.mode != CardCrawlGame.GameMode.GAMEPLAY ||
                CardCrawlGame.dungeon == null || AbstractDungeon.currMapNode == null ||
                AbstractDungeon.player == null) return;
        out.setProperty("ui.masterDeck.count", Integer.toString(AbstractDungeon.player.masterDeck.size()));
        Object event = AbstractDungeon.getCurrRoom().event;
        if (event != null) {
            out.setProperty("ui.event.class", event.getClass().getName());
            Object dialog = DualRender.get(event, "imageEventText");
            items(out, "eventOptions", DualRender.get(dialog, "optionList"));
            items(out, "roomOptions", com.megacrit.cardcrawl.events.RoomEventDialog.optionList);
        }
        if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.FTUE && AbstractDungeon.ftue != null) {
            out.setProperty("ui.tutorial.class", AbstractDungeon.ftue.getClass().getName());
            field(out, "ui.tutorial.slot", AbstractDungeon.ftue, "currentSlot");
            hit(out, "tutorialConfirm", DualRender.get(AbstractDungeon.ftue, "button"));
        }
        field(out, "ui.viewingRelics", AbstractDungeon.player, "viewingRelics");
        field(out, "ui.inspect", AbstractDungeon.player, "inspectMode");
        Object inspect = AbstractDungeon.player.inspectHb;
        if (inspect instanceof Hitbox) {
            out.setProperty("ui.inspect.x", Float.toString(((Hitbox)inspect).cX));
            out.setProperty("ui.inspect.y", Float.toString(((Hitbox)inspect).cY));
        }
        int relicIndex = 0;
        for (com.megacrit.cardcrawl.relics.AbstractRelic relic : AbstractDungeon.player.relics) {
            out.setProperty("ui.relic." + relicIndex + ".hovered", Boolean.toString(relic.hb.hovered));
            relicIndex++;
        }
        Object panel = AbstractDungeon.topPanel;
        field(out, "ui.topPanel", panel, "selectPotionMode");
        Object popup = DualRender.get(panel, "potionUi");
        field(out, "ui.potion.hidden", popup, "isHidden");
        field(out, "ui.potion.target", popup, "targetMode");
        field(out, "ui.potion.slot", popup, "slot");
        field(out, "ui.potion.monster", DualRender.get(popup, "hoveredMonster"), "id");
        int i = 0;
        for (AbstractPotion potion : AbstractDungeon.player.potions) {
            out.setProperty("ui.potion." + i + ".id", potion.ID);
            out.setProperty("ui.potion." + i + ".hovered", Boolean.toString(potion.hb.hovered));
            i++;
        }
        hit(out, "confirm", DualRender.get(AbstractDungeon.cardRewardScreen, "confirmButton"));
        hit(out, "skip", DualRender.get(AbstractDungeon.cardRewardScreen, "skipButton"));
        items(out, "cards", DualRender.get(AbstractDungeon.cardRewardScreen, "rewardGroup"));
        items(out, "gridCards", AbstractDungeon.gridSelectScreen.targetGroup == null ? null :
                AbstractDungeon.gridSelectScreen.targetGroup.group);
        items(out, "handCards", AbstractDungeon.player.hand.group);
        field(out, "ui.grid.confirm", AbstractDungeon.gridSelectScreen, "confirmScreenUp");
        out.setProperty("ui.hand.selected",
                Integer.toString(AbstractDungeon.handCardSelectScreen.selectedCards.size()));
        items(out, "selectedHandCards", AbstractDungeon.handCardSelectScreen.selectedCards.group);
        field(out, "ui.hand.required", AbstractDungeon.handCardSelectScreen, "numCardsToSelect");
        out.setProperty("ui.grid.selected", Integer.toString(AbstractDungeon.gridSelectScreen.selectedCards.size()));
        items(out, "rewards", DualRender.get(AbstractDungeon.combatRewardScreen, "rewards"));
        hit(out, "gridConfirm", DualRender.get(AbstractDungeon.gridSelectScreen, "confirmButton"));
        hit(out, "handConfirm", DualRender.get(AbstractDungeon.handCardSelectScreen, "button"));
        Object camp = DualRender.get(AbstractDungeon.getCurrRoom(), "campfireUI");
        items(out, "campfire", DualRender.get(camp, "buttons"));
        Object overlay = AbstractDungeon.overlayMenu;
        hit(out, "cancel", DualRender.get(overlay, "cancelButton"));
        hit(out, "proceed", DualRender.get(overlay, "proceedButton"));
    }
}
