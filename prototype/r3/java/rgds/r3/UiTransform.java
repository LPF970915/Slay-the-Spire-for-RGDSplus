package rgds.r3;

/** The same affine coordinates drive drawing and inverse pointer hit tests. */
public final class UiTransform {
    public static final UiTransform IDENTITY = new UiTransform(1, 0, 0);
    private static final UiTransform HAND_NORMAL = anchored(1.50f, 512, 0, 512, 315);
    private static final UiTransform HAND_MEDIUM = anchored(1.30f, 512, 0, 512, 315);
    private static final UiTransform HAND_CROWDED = anchored(1.12f, 512, 0, 512, 315);
    public final float scale, dx, dy;

    public UiTransform(float scale, float dx, float dy) {
        if (!(scale > 0)) throw new IllegalArgumentException("Positive scale required");
        this.scale = scale;
        this.dx = dx;
        this.dy = dy;
    }

    public static UiTransform anchored(float scale, float x, float y, float toX, float toY) {
        return new UiTransform(scale, toX - x * scale, toY - y * scale);
    }

    public static UiTransform hand(int count) {
        return count >= 8 ? HAND_CROWDED : count >= 6 ? HAND_MEDIUM : HAND_NORMAL;
    }

    public float x(float x) { return x * scale + dx; }
    public float y(float y) { return y * scale + dy; }
    public float inverseX(float x) { return (x - dx) / scale; }
    public float inverseY(float y) { return (y - dy) / scale; }
}
