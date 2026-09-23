package rgds.r3;

import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.helpers.FontHelper;
import com.megacrit.cardcrawl.helpers.input.InputHelper;
import com.megacrit.cardcrawl.screens.SingleCardViewPopup;
import com.megacrit.cardcrawl.screens.SingleRelicViewPopup;
import com.megacrit.cardcrawl.ui.buttons.CancelButton;

/** A visible lower-panel close control for the native upper detail modals. */
public final class DetailControls {
    private static CancelButton back;
    private static Object owner;

    public static boolean update(Object popup) {
        if (!Boolean.TRUE.equals(DualRender.get(popup, "isOpen"))) return false;
        if (back == null) back = new CancelButton();
        if (owner != popup) {
            owner = popup;
            back.showInstantly(CancelButton.TEXT[0]);
            back.hb.clicked = back.hb.clickStarted = false;
        }
        // CancelButton.update closes dungeon/menu screens itself. This button
        // only borrows its native visual and hitbox, not that navigation logic.
        back.hb.update();
        if (TouchInput.ownsPointer() && back.hb.hovered && InputHelper.justClickedLeft) {
            back.hb.clickStarted = true;
            InputHelper.justClickedLeft = false;
        }
        if (!back.hb.clicked) return false;
        back.hb.clicked = false;
        InputHelper.justClickedLeft = InputHelper.justReleasedClickLeft = false;
        if (popup instanceof SingleCardViewPopup) {
            ((SingleCardViewPopup)popup).close();
            FontHelper.ClearSCPFontTextures();
        } else {
            ((SingleRelicViewPopup)popup).close();
            FontHelper.ClearSRVFontTextures();
        }
        TouchInput.state.cancel();
        DualRender.cancelTouchHits();
        return true;
    }

    public static boolean outsideClick(Object popup, boolean value, boolean release) {
        if (!TouchInput.ownsPointer()) return value;
        if (release) return false;
        // Native arrow selection still handles its own down/up. Empty lower
        // space is not the upper card/relic's outside-click dismissal region.
        for (String name : new String[]{"prevHb", "nextHb", "upgradeHb", "betaArtHb"}) {
            Object hb = DualRender.get(popup, name);
            if (hb instanceof com.megacrit.cardcrawl.helpers.Hitbox &&
                    ((com.megacrit.cardcrawl.helpers.Hitbox)hb).hovered) return value;
        }
        return false;
    }

    public static void render(SpriteBatch batch) {
        boolean open = CardCrawlGame.cardPopup != null && CardCrawlGame.cardPopup.isOpen ||
                CardCrawlGame.relicPopup != null && CardCrawlGame.relicPopup.isOpen;
        if (!open) { owner = null; return; }
        if (back == null) return;
        DualRender.push(batch, 1, false);
        try { back.render(batch); }
        finally { DualRender.pop(batch); }
    }

    public static void diagnostics(java.util.Properties out) {
        if (back != null && owner != null) DualRender.touchPosition(out, "ui.detailClose", back.hb);
    }
}
