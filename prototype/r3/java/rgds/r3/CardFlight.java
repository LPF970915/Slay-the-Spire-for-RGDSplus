package rgds.r3;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardQueueItem;
import com.megacrit.cardcrawl.core.AbstractCreature;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.Map;
import java.util.WeakHashMap;

/** A single native card render, mirrored at GPU submission, never a second rules object. */
public final class CardFlight {
    private static final Map<AbstractCard, Flight> flights = new WeakHashMap<>();
    private static final Map<AbstractCard, Boolean> consumed = new WeakHashMap<>();
    private static final ArrayList<AbstractCard> drawing = new ArrayList<>();
    private static AbstractCard visual;
    private static Object room;
    private static long launched, lowerFrames, upperFrames;
    private static float lastX, lastY, lastScale;

    private static final class Flight {
        float x, y, scale, angle, tx, ty, age;
        boolean started, arrived;
    }

    public static boolean visual() { return visual != null; }
    public static boolean visual(AbstractCard card) { return visual == card; }
    public static boolean owns(AbstractCard card) {
        return card != null && (flights.containsKey(card) || consumed.containsKey(card));
    }
    public static boolean hide(AbstractCard card) {
        return visual != card && owns(card) && !AbstractDungeon.isScreenUp;
    }

    public static void queued(AbstractCard card, AbstractCreature target, UiTransform hand) {
        Flight f = new Flight();
        f.x = hand.x(card.current_x);
        f.y = 816 + 768 - hand.y(card.current_y);
        f.scale = card.drawScale * hand.scale;
        f.angle = card.angle;
        if (target == null && card.target == AbstractCard.CardTarget.SELF)
            target = AbstractDungeon.player;
        // Area and untargeted cards travel to the battle field, never invent a single enemy.
        f.tx = target == null ? 512 : target.hb.cX;
        f.ty = target == null ? 384 : 768 - target.hb.cY;
        flights.put(card, f);
        room = AbstractDungeon.getCurrRoom();
    }

    public static void used(AbstractCard card) {
        Flight f = flights.get(card);
        if (f != null && !f.started) {
            f.started = true;
            consumed.put(card, Boolean.TRUE);
            launched++;
            System.out.println("[r4-flight] start card=" + card.cardID +
                    " from=" + f.x + "," + f.y + " to=" + f.tx + "," + f.ty);
        }
    }

    public static void tick() {
        if (room != null && (CardCrawlGame.mode != CardCrawlGame.GameMode.GAMEPLAY ||
                AbstractDungeon.player == null || AbstractDungeon.getCurrRoom() != room)) {
            flights.clear(); consumed.clear(); room = null;
            return;
        }
        if (room == null) return;
        float dt = Math.max(0, Math.min(.05f, Gdx.graphics.getDeltaTime()));
        Iterator<Map.Entry<AbstractCard, Flight>> it = flights.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<AbstractCard, Flight> item = it.next();
            Flight f = item.getValue();
            if (!f.started) {
                boolean queued = false;
                for (CardQueueItem q : AbstractDungeon.actionManager.cardQueue)
                    queued |= q.card == item.getKey();
                if (!queued) it.remove();
            } else {
                f.age = Math.min(CardFlightPath.DURATION, f.age + dt);
                if (f.arrived || AbstractDungeon.isScreenUp && f.age >= CardFlightPath.DURATION)
                    it.remove();
            }
        }
        consumed.keySet().removeIf(card -> !flights.containsKey(card) &&
                AbstractDungeon.player.hand.group.contains(card));
    }

    public static void render(SpriteBatch batch) {
        if (AbstractDungeon.isScreenUp || flights.isEmpty()) return;
        drawing.clear();
        drawing.addAll(flights.keySet());
        for (AbstractCard card : drawing) {
            Flight f = flights.get(card);
            if (f == null) continue;
            float x = card.current_x, y = card.current_y, scale = card.drawScale, angle = card.angle;
            Color color = new Color(batch.getColor());
            lastX = CardFlightPath.position(f.x, f.tx, f.age);
            lastY = CardFlightPath.position(f.y, f.ty, f.age);
            lastScale = CardFlightPath.scale(f.scale, f.age);
            card.current_x = lastX;
            card.current_y = 1584 - lastY;
            card.drawScale = lastScale;
            card.angle = f.angle * (1 - CardFlightPath.progress(f.age));
            visual = card;
            DualRender.pushFlight(batch);
            try {
                card.render(batch);
                if (lastY >= 768) lowerFrames++;
                if (lastY <= 816) upperFrames++;
                f.arrived = f.age >= CardFlightPath.DURATION;
            } finally {
                try { DualRender.endPage(batch, true); }
                finally {
                    visual = null;
                    card.current_x = x; card.current_y = y; card.drawScale = scale; card.angle = angle;
                    batch.setColor(color);
                }
            }
        }
        drawing.clear();
    }

    public static void diagnostics(java.util.Properties state) {
        state.setProperty("flight.launched", Long.toString(launched));
        state.setProperty("flight.active", Integer.toString(flights.size()));
        state.setProperty("flight.lowerFrames", Long.toString(lowerFrames));
        state.setProperty("flight.upperFrames", Long.toString(upperFrames));
        state.setProperty("flight.lastX", Float.toString(lastX));
        state.setProperty("flight.lastY", Float.toString(lastY));
        state.setProperty("flight.lastScale", Float.toString(lastScale));
    }
}
