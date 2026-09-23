package rgds.r3;

import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.Hitbox;
import com.megacrit.cardcrawl.ui.MultiPageFtue;

/** The tutorial owns Proceed: its touch release must not open the dungeon map. */
public final class TutorialTouch {
    private static Object owner;
    private static Hitbox pressed;
    private static boolean clicked;

    public static boolean active() {
        return AbstractDungeon.screen == AbstractDungeon.CurrentScreen.FTUE
                && AbstractDungeon.ftue instanceof MultiPageFtue;
    }

    public static void update(Object tutorial) {
        clicked = false;
        if (owner != tutorial || !TouchInput.ownsPointer()) pressed = null;
        owner = tutorial;
        if (!TouchInput.ownsPointer()) return;
        Hitbox hb = (Hitbox)DualRender.get(AbstractDungeon.overlayMenu.proceedButton, "hb");
        boolean hit = hb != null && DualRender.touchOrder(
                hb, TouchInput.state.x, TouchInput.state.y) >= 0;
        if (TouchInput.state.justDown) pressed = hit ? hb : null;
        if (TouchInput.state.justUp) {
            clicked = hit && pressed == hb;
            pressed = null;
        }
        AbstractDungeon.overlayMenu.proceedButton.isHovered = hit;
    }

    public static boolean click(boolean original) {
        return TouchInput.ownsPointer() ? clicked : original;
    }
}
