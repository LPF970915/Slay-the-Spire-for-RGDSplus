package rgds.r3;

import java.util.ArrayDeque;

/** Ordered mouse edges from one evdev contact; no game calls or background thread. */
public final class TouchState {
    public static final int HEARTBEAT = 0, DOWN = 1, MOVE = 2, UP = 3, CANCEL = 4;
    private static final double MAX_AGE = 1.5;
    private final ArrayDeque<Event> pending = new ArrayDeque<Event>();
    public boolean owned, down, justDown, justUp, cancelled;
    public int x, y, dx, dy;
    public float excursion;
    private int startX, startY;
    private long gesture;
    private double lastPacket;

    private static final class Event {
        final int kind;
        final double time;
        final int x, y;
        final long gesture;
        int minX, maxX, minY, maxY;
        Event(int kind, double time, float x, float y, long gesture) {
            this.kind = kind; this.time = time;
            this.x = Math.round(x); this.y = Math.round(y); this.gesture = gesture;
            minX = maxX = this.x; minY = maxY = this.y;
        }
    }

    public void accept(int kind, double time, float x, float y, long token, double now) {
        if (!Double.isFinite(time) || time > now + .1 || now - time > MAX_AGE ||
                !Float.isFinite(x) || !Float.isFinite(y) || kind < 0 || kind > CANCEL) {
            cancel();
            return;
        }
        lastPacket = now;
        if (kind == CANCEL) { cancel(); return; }
        if (kind == HEARTBEAT) return;
        if (x < 0 || x > 1024 || y < 0 || y > 768 || token <= 0 || pending.size() >= 128) {
            cancel();
            return;
        }
        Event tail = pending.peekLast();
        Event event = new Event(kind, time, x, y, token);
        if (kind == MOVE && tail != null && tail.kind == MOVE && tail.gesture == token) {
            event.minX = Math.min(tail.minX, event.minX);
            event.maxX = Math.max(tail.maxX, event.maxX);
            event.minY = Math.min(tail.minY, event.minY);
            event.maxY = Math.max(tail.maxY, event.maxY);
            pending.removeLast();
        }
        pending.addLast(event);
    }

    public void cancel() {
        pending.clear();
        owned = down = justDown = justUp = false;
        gesture = 0;
        excursion = 0;
        cancelled = true;
    }

    public boolean hasPending() { return !pending.isEmpty(); }

    public boolean advance(double now) {
        justDown = justUp = false;
        dx = dy = 0;
        if (owned && now - lastPacket > MAX_AGE) cancel();
        if (cancelled) { cancelled = false; return true; }
        while (!pending.isEmpty()) {
            Event event = pending.removeFirst();
            if (now - event.time > MAX_AGE) {
                cancel(); cancelled = false; return true;
            }
            if (event.kind == DOWN) {
                if (down) { cancel(); cancelled = false; return true; }
                gesture = event.gesture;
                owned = down = justDown = true;
                startX = event.x; startY = event.y; excursion = 0;
            } else if (!down || event.gesture != gesture) {
                continue;
            }
            dx = event.x - x;
            dy = event.y - y;
            x = event.x; y = event.y;
            float farX = Math.max(Math.abs(event.minX - startX), Math.abs(event.maxX - startX));
            float farY = Math.max(Math.abs(event.minY - startY), Math.abs(event.maxY - startY));
            excursion = Math.max(excursion, (float)Math.hypot(farX, farY));
            if (event.kind == UP) { down = false; justUp = true; }
            // Never collapse DOWN and UP into the same native update.
            break;
        }
        return false;
    }
}
