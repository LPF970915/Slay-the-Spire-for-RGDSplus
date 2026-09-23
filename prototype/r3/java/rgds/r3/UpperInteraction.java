package rgds.r3;

import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.GameCursor;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.controller.CInputActionSet;
import com.megacrit.cardcrawl.ui.panels.PotionPopUp;

/** The upper panel remains controller-owned; a lower contact never uses a potion. */
public final class UpperInteraction {
    private static boolean dungeon() {
        return CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                CardCrawlGame.dungeon != null && AbstractDungeon.topPanel != null;
    }

    public static String context() {
        if (!dungeon()) return "";
        PotionPopUp ui = AbstractDungeon.topPanel.potionUi;
        return ui.isHidden + "/" + ui.targetMode + "/" + AbstractDungeon.topPanel.selectPotionMode +
                "/" + (AbstractDungeon.player != null && AbstractDungeon.player.viewingRelics) +
                "/" + (AbstractDungeon.player != null && AbstractDungeon.player.inspectMode);
    }

    public static boolean cancelForTouch() {
        if (!dungeon()) return false;
        PotionPopUp ui = AbstractDungeon.topPanel.potionUi;
        boolean active = !ui.isHidden || ui.targetMode || AbstractDungeon.topPanel.selectPotionMode ||
                AbstractDungeon.player != null &&
                        (AbstractDungeon.player.viewingRelics || AbstractDungeon.player.inspectMode);
        if (!active) return false;
        cancelPotion(ui);
        AbstractDungeon.topPanel.selectPotionMode = false;
        AbstractDungeon.topPanel.unhoverHitboxes();
        if (AbstractDungeon.player != null) {
            AbstractDungeon.player.viewingRelics = false;
            AbstractDungeon.player.inspectMode = false;
            AbstractDungeon.player.inspectHb = null;
            AbstractDungeon.player.releaseCard();
        }
        return true;
    }

    public static void cancelPotion(PotionPopUp ui) {
        ui.targetMode = false;
        ui.close();
        GameCursor.hidden = false;
    }

    public static boolean guardTarget(PotionPopUp ui) {
        if (!TouchInput.enabled) return false;
        // The native cancellation branch continues into its use branch. Return
        // immediately so simultaneous cancel/select cannot consume the potion.
        if (TouchInput.ownsPointer() || CInputActionSet.cancel.isJustPressed()) {
            cancelPotion(ui);
            CInputActionSet.cancel.unpress();
            CInputActionSet.select.unpress();
            return true;
        }
        return false;
    }
}
