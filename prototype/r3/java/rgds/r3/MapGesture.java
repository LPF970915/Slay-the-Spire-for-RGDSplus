package rgds.r3;

/** One lower-local contact; returning to the start never turns a drag into a tap. */
public final class MapGesture {
    public static final float SLOP = 12;
    public boolean active, dragging, scrollable;
    public Object pressed;
    private float startX, startY, lastY, offset;

    public void begin(float x, float y, float currentOffset, Object hit, boolean canScroll) {
        active = true;
        dragging = false;
        scrollable = canScroll;
        pressed = hit;
        startX = x; startY = lastY = y; offset = currentOffset;
    }

    public float move(float x, float y, float excursion, float lower, float upper) {
        if (!active) return offset;
        if (Math.hypot(x - startX, y - startY) >= SLOP || excursion >= SLOP)
            dragging = true;
        if (dragging && scrollable) {
            offset = Math.max(lower, Math.min(upper, offset + lastY - y));
            lastY = y;
        }
        return offset;
    }

    public boolean release(Object hit, float x, float y) {
        boolean tap = active && !dragging && pressed != null && pressed == hit &&
                x > 2 && x < 1022 && y > 2 && y < 766;
        active = false;
        return tap;
    }

    public void cancel() {
        active = dragging = scrollable = false;
        pressed = null;
    }
}
