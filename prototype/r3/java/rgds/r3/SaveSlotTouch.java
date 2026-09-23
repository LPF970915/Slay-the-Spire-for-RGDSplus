package rgds.r3;

import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.helpers.Hitbox;
import com.megacrit.cardcrawl.screens.mainMenu.SaveSlot;

/** Resolve save-card action icons before the card-wide slot hitbox. */
public final class SaveSlotTouch {
    public static boolean update(SaveSlot slot) {
        if (!TouchInput.ownsPointer() || slot.emptySlot) return false;
        Object rename = DualRender.get(slot, "renameHb");
        Object delete = DualRender.get(slot, "deleteHb");
        int x = TouchInput.state.x, y = TouchInput.state.y;
        Hitbox renameHb = rename instanceof Hitbox ? (Hitbox)rename : null;
        Hitbox deleteHb = delete instanceof Hitbox ? (Hitbox)delete : null;
        if (TouchInput.state.justDown) {
            System.out.println("[r4-save-touch] down x=" + x + " y=" + y +
                    " rename=" + (renameHb == null ? -1 : DualRender.touchOrder(renameHb, x, y)) +
                    " delete=" + (deleteHb == null ? -1 : DualRender.touchOrder(deleteHb, x, y)));
            if (renameHb != null && DualRender.touchOrder(renameHb, x, y) >= 0) {
                renameHb.hovered = true; renameHb.clickStarted = true;
                return true;
            }
            if (deleteHb != null && DualRender.touchOrder(deleteHb, x, y) >= 0) {
                deleteHb.hovered = true; deleteHb.clickStarted = true;
                return true;
            }
        }
        if (!TouchInput.state.justUp) return renameHb != null && renameHb.clickStarted ||
                deleteHb != null && deleteHb.clickStarted;
        Object active = renameHb != null && renameHb.clickStarted ? renameHb :
                deleteHb != null && deleteHb.clickStarted ? deleteHb : null;
        if (active == null || DualRender.touchOrder((Hitbox)active, x, y) < 0) return false;
        Integer index = (Integer)DualRender.get(slot, "index");
        if (index == null) return false;
        if (active == renameHb)
            CardCrawlGame.mainMenuScreen.saveSlotScreen.openRenamePopup(index, false);
        else
            CardCrawlGame.mainMenuScreen.saveSlotScreen.openDeletePopup(index);
        System.out.println("[r4-save-touch] open " + (active == renameHb ? "rename" : "delete") +
                " slot=" + index);
        renameHb.clickStarted = deleteHb.clickStarted = false;
        return true;
    }
}
