import rgds.InputEdges;

public final class InputEdgesTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    private static boolean tick(int key) {
        InputEdges.beginFrame();
        return InputEdges.pressed(key);
    }
    public static void main(String[] args) {
        InputEdges.reset();
        InputEdges.down(62);
        InputEdges.up(62);
        check(tick(62), "same-poll tap survives");
        check(InputEdges.pressed(62), "multiple polls in one frame agree");
        check(!tick(62), "tap releases next frame");
        check(!tick(62), "no duplicate tap");

        InputEdges.down(62);
        check(tick(62), "held press");
        InputEdges.down(62);
        check(tick(62) && tick(62), "autorepeat is not a new press");
        InputEdges.up(62);
        check(!tick(62), "held release");

        for (int i = 0; i < 5; i++) { InputEdges.down(62); InputEdges.up(62); }
        check(tick(62) && !tick(62) && tick(62) && !tick(62), "two pending taps");
        check(!tick(62), "backlog bounded");
        InputEdges.down(62);
        InputEdges.up(62);
        InputEdges.discardPending();
        check(!tick(62), "screen transition drops unprocessed taps");

        InputEdges.down(62);
        check(tick(62), "press opens dialog");
        InputEdges.discardPending();
        InputEdges.up(62);
        check(!tick(62), "dialog release preserved");
        InputEdges.down(131);
        InputEdges.up(131);
        InputEdges.down(21);
        InputEdges.up(21);
        InputEdges.beginFrame();
        check(InputEdges.pressed(131) && InputEdges.pressed(21), "independent simultaneous keys");
        InputEdges.beginFrame();
        check(!InputEdges.pressed(131) && !InputEdges.pressed(21), "simultaneous releases");
        InputEdges.down(-1);
        InputEdges.up(999);
        check(!InputEdges.pressed(-1) && !InputEdges.pressed(256), "bounds");
        System.out.println("PASS: tap, hold, autorepeat, frame cache, bounded queue, dialog and bounds");
    }
}
