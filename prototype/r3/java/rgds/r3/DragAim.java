package rgds.r3;

/** R4 drag regions and sticky targets, independent of the game's rules and input source. */
public final class DragAim {
    public static final float ACTIVATE = 24, SWITCH = 64;
    private float originY, switchX;
    public boolean active;

    public void begin(float x, float y) {
        originY = y;
        switchX = x;
        active = false;
    }

    public void clear() { active = false; }

    public int update(float x, float y, float cardX, float cardY,
                      float[][] boxes, int count, int previous) {
        float rise = originY - y;
        if (rise <= 0) {
            active = false;
            switchX = x;
            return -1;
        }
        if (!active) {
            if (rise < ACTIVATE) return -1;
            active = true;
            switchX = x;
            return nearest(cardX, cardY, boxes, count);
        }
        // A lost target must never silently turn into a different target.
        if (previous < 0 || previous >= count) return -1;
        int selected = previous;
        while (Math.abs(x - switchX) >= SWITCH) {
            int direction = x > switchX ? 1 : -1;
            int next = neighbour(boxes, count, selected, direction);
            if (next == selected) {
                switchX = x;
                break;
            }
            selected = next;
            switchX += direction * SWITCH;
        }
        return selected;
    }

    private static int nearest(float x, float y, float[][] boxes, int count) {
        int selected = -1;
        double best = Double.POSITIVE_INFINITY;
        for (int i = 0; i < count; i++) {
            double distance = Math.hypot(boxes[i][0] - x, boxes[i][1] - y);
            if (distance < best) { best = distance; selected = i; }
        }
        return selected;
    }

    private static int compare(float[][] boxes, int a, int b) {
        int order = Float.compare(boxes[a][0], boxes[b][0]);
        if (order == 0) order = Float.compare(boxes[a][1], boxes[b][1]);
        return order == 0 ? Integer.compare(a, b) : order;
    }

    private static int neighbour(float[][] boxes, int count, int current, int direction) {
        int best = current;
        for (int i = 0; i < count; i++) {
            if (compare(boxes, i, current) * direction <= 0) continue;
            if (best == current || compare(boxes, i, best) * direction < 0) best = i;
        }
        return best;
    }

    public boolean canRelease(float x, float y) {
        // The panel's outermost strip cannot distinguish lift-off from sliding off.
        return active && y < originY && x > 2 && x < 1022 && y > 2 && y < 766;
    }
}
