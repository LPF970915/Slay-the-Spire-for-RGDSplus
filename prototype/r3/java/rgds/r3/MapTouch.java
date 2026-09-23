package rgds.r3;

import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.Hitbox;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.screens.DungeonMapScreen;
import java.util.Properties;

/** Supplies input edges only; the native map retains all path and room rules. */
public final class MapTouch {
    private static final MapGesture gesture = new MapGesture();
    private static Hitbox released;
    private static boolean owns, scrolling;
    private static float scrollOffset, minimum, maximum;
    private static long taps, drags;

    private static boolean mapOpen() {
        return TouchInput.enabled && CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                AbstractDungeon.screen == AbstractDungeon.CurrentScreen.MAP &&
                AbstractDungeon.dungeonMapScreen != null;
    }

    public static boolean controls() { return mapOpen() && TouchInput.ownsPointer(); }

    private static boolean node(Hitbox hb) {
        if (hb == null) return false;
        if (hb == AbstractDungeon.dungeonMapScreen.map.bossHb) return true;
        for (java.util.ArrayList<MapRoomNode> row : AbstractDungeon.map)
            for (MapRoomNode n : row)
                if (n.hb == hb) return true;
        return false;
    }

    public static void cancel() {
        gesture.cancel();
        released = null;
        scrolling = false;
        if (owns && AbstractDungeon.dungeonMapScreen != null)
            AbstractDungeon.dungeonMapScreen.clicked = false;
        owns = false;
    }

    private static float number(Object value, float fallback) {
        return value instanceof Number ? ((Number)value).floatValue() : fallback;
    }

    public static void begin(DungeonMapScreen screen, float wait) {
        released = null;
        if (!controls()) { cancel(); return; }
        owns = true;
        screen.clicked = false;
        minimum = number(DualRender.get(screen, "mapScrollUpperLimit"), -2300);
        maximum = number(DualRender.get(DungeonMapScreen.class, "MAP_SCROLL_LOWER"), 190);
        TouchState touch = TouchInput.state;
        if (wait >= 0 || CardCrawlGame.isPopupOpen || AbstractDungeon.isFadingOut) {
            gesture.cancel();
            scrolling = false;
            return;
        }
        Hitbox hit = DualRender.touchHitAt(touch.x, touch.y);
        if (touch.justDown) {
            gesture.begin(touch.x, touch.y, DungeonMapScreen.offsetY, hit, hit == null || node(hit));
            scrolling = false;
        }
        if (gesture.active) {
            boolean wasDrag = gesture.dragging;
            scrollOffset = gesture.move(touch.x, touch.y, touch.excursion, minimum, maximum);
            scrolling = gesture.dragging && gesture.scrollable;
            if (!wasDrag && gesture.dragging) drags++;
            if (touch.justUp) {
                if (gesture.release(hit, touch.x, touch.y)) {
                    released = hit;
                    screen.clicked = node(hit) && hit != screen.map.bossHb;
                    taps++;
                }
                gesture.pressed = null;
            }
        }
    }

    public static float scroll(float target) {
        return scrolling ? scrollOffset : target;
    }

    public static boolean suppressHit(Hitbox hb) {
        if (!controls()) return false;
        if (gesture.dragging) return true;
        if (TouchInput.state.justUp) return released != hb;
        return gesture.active && gesture.pressed != hb;
    }

    public static boolean bossClick(boolean nativeClick) {
        return controls() ? released == AbstractDungeon.dungeonMapScreen.map.bossHb : nativeClick;
    }

    public static void diagnostics(Properties state) {
        if (!mapOpen()) return;
        state.setProperty("map.offset", Float.toString(DungeonMapScreen.offsetY));
        state.setProperty("map.minimum", Float.toString(minimum));
        state.setProperty("map.maximum", Float.toString(maximum));
        state.setProperty("map.dragging", Boolean.toString(gesture.dragging));
        state.setProperty("map.taps", Long.toString(taps));
        state.setProperty("map.drags", Long.toString(drags));
        MapRoomNode current = AbstractDungeon.getCurrMapNode();
        state.setProperty("map.current", current.x + "," + current.y);
        int i = 0;
        for (java.util.ArrayList<MapRoomNode> row : AbstractDungeon.map) {
            for (MapRoomNode n : row) {
                if (!n.hasEdges()) continue;
                String prefix = "map.node." + i++;
                state.setProperty(prefix + ".id", n.x + "," + n.y);
                state.setProperty(prefix + ".legal", Boolean.toString(
                        AbstractDungeon.getCurrRoom().phase ==
                            com.megacrit.cardcrawl.rooms.AbstractRoom.RoomPhase.COMPLETE &&
                        (AbstractDungeon.firstRoomChosen ?
                            current.isConnectedTo(n) || current.wingedIsConnectedTo(n) : n.y == 0)));
                DualRender.touchPosition(state, prefix, n.hb);
            }
        }
        state.setProperty("map.nodes", Integer.toString(i));
        DualRender.touchPosition(state, "map.boss", AbstractDungeon.dungeonMapScreen.map.bossHb);
    }
}
