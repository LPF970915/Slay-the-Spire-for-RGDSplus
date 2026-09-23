package rgds.r3;

import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.Soul;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import java.util.Map;
import java.util.WeakHashMap;

/** Origin tags for globally queued visual effects; native updates and pools remain intact. */
public final class CombatEffects {
    private static final Map<Object, String> kinds = new WeakHashMap<>();
    private static Soul updatingSoul;
    private static long lowerEffects, upperReticles, hiddenCursors;

    public static boolean combat() {
        return AbstractDungeon.player != null && AbstractDungeon.getCurrRoom() != null &&
                AbstractDungeon.getCurrRoom().phase ==
                com.megacrit.cardcrawl.rooms.AbstractRoom.RoomPhase.COMBAT;
    }

    public static void soulBegin(Soul soul) { updatingSoul = soul; }
    public static void soulEnd() { updatingSoul = null; }

    private static String soulKind(Soul soul) {
        if (CardFlight.owns(soul.card)) return "hidden";
        if (soul.group == AbstractDungeon.player.drawPile ||
                soul.group == AbstractDungeon.player.discardPile) return "lower";
        return "native";
    }

    public static void trail(Object effect) {
        kinds.remove(effect);
        if (updatingSoul != null && combat())
            kinds.put(effect, soulKind(updatingSoul));
    }

    public static boolean hidden(Object effect) { return "hidden".equals(kinds.get(effect)); }

    public static void particle(Object effect, float x) {
        if (combat()) kinds.put(effect, x < 512 ? "draw" : "discard");
    }

    public static void begin(SpriteBatch batch, Object effect, String kind) {
        String tagged = kinds.get(effect);
        if (tagged != null) kind = tagged;
        if (!combat()) { DualRender.preserve(batch); return; }
        if (effect instanceof Soul) kind = soulKind((Soul)effect);
        if (kind.equals("lower")) DualRender.push(batch, 1, false);
        else if (kind.equals("exhaust")) DualRender.push(batch, 1, false);
        else if (kind.equals("native") || kind.equals("hidden")) DualRender.preserve(batch);
        else DualRender.pushEffect(batch, effect, kind);
        lowerEffects++;
    }

    public static void reticle(SpriteBatch batch) {
        DualRender.push(batch, 0, false);
        upperReticles++;
    }

    public static boolean cursor() {
        if (!TouchInput.hideCursor()) return false;
        hiddenCursors++;
        return true;
    }

    public static void diagnostics(java.util.Properties state) {
        state.setProperty("vfx.lowerScopes", Long.toString(lowerEffects));
        state.setProperty("vfx.upperReticles", Long.toString(upperReticles));
        state.setProperty("vfx.hiddenCursors", Long.toString(hiddenCursors));
    }
}
