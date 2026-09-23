package rgds.r3;

/** Visual-only coordinates: upper 0..768, bezel 768..816, lower 816..1584. */
public final class CardFlightPath {
    public static final float DURATION = .42f;
    public static float progress(float seconds) {
        float t = Math.max(0, Math.min(1, seconds / DURATION));
        return t * t * (3 - 2 * t);
    }
    public static float position(float start, float end, float seconds) {
        return start + (end - start) * progress(seconds);
    }
    public static float scale(float initial, float seconds) {
        return initial * (1 - .94f * progress(seconds));
    }
}
