package rgds;

/** Preserve short taps when a backend delivers press and release in one poll. */
public final class InputEdges {
    private static final boolean[] physical = new boolean[256];
    private static final boolean[] emitted = new boolean[256];
    private static final int[] pending = new int[256];
    private static final long[] sampled = new long[256];
    private static long frame = 1;

    private InputEdges() {}

    public static void beginFrame() { frame++; }

    public static void down(int key) {
        if (key < 0 || key >= physical.length || physical[key]) return;
        physical[key] = true;
        // At most two taps: do not replay a long backlog after loading a scene.
        pending[key] = Math.min(2, pending[key] + 1);
    }

    public static void up(int key) {
        if (key >= 0 && key < physical.length) physical[key] = false;
    }

    public static boolean pressed(int key) {
        if (key < 0 || key >= physical.length) return false;
        if (sampled[key] != frame) {
            if (emitted[key]) {
                if (!physical[key] || pending[key] > 0) emitted[key] = false;
            } else if (pending[key] > 0) {
                pending[key]--;
                emitted[key] = true;
            }
            sampled[key] = frame;
        }
        return emitted[key];
    }

    public static void discardPending() {
        java.util.Arrays.fill(pending, 0);
    }

    public static void reset() {
        java.util.Arrays.fill(physical, false);
        java.util.Arrays.fill(emitted, false);
        java.util.Arrays.fill(pending, 0);
        java.util.Arrays.fill(sampled, 0);
        frame = 1;
    }
}
