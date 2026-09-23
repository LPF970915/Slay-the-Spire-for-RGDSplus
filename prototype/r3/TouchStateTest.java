import rgds.r3.TouchState;

public final class TouchStateTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        TouchState s = new TouchState();
        s.accept(1, 10, 100, 200, 1, 10);
        s.accept(2, 10, 200, 300, 1, 10);
        s.accept(3, 10, 200, 300, 1, 10);
        check(!s.advance(10) && s.down && s.justDown && s.x == 100, "DOWN frame");
        check(!s.advance(10.03) && s.down && !s.justDown && s.x == 200, "MOVE frame");
        check(!s.advance(10.06) && !s.down && s.owned && s.justUp && s.y == 300, "UP frame");
        check(!s.advance(10.09) && !s.justUp, "UP is one update only");
        s.accept(1, 11, 10, 20, 2, 11);
        s.advance(11);
        s.accept(3, 11, 10, 20, 1, 11);
        check(!s.advance(11.03) && s.down, "stale UP");
        s.accept(3, 11, 10, 20, 2, 11);
        s.accept(4, 11, 0, 0, 2, 11);
        check(s.advance(11.06) && !s.down && !s.owned, "cancel wins queued UP");
        s.accept(1, 12, 0, 0, 3, 12);
        s.advance(12);
        check(s.advance(14) && !s.down, "lost heartbeat cancels hold");
        s.accept(1, 12, 0, 0, 4, 14);
        check(s.advance(14) && !s.down, "stale packet rejected");
        s.accept(1, 15, Float.NaN, 0, 4, 15);
        check(s.advance(15) && !s.down, "invalid coordinate rejected");
        s.accept(1, 16, 1024, 768, 5, 16);
        s.advance(16);
        for (int i = 0; i < 300; i++) s.accept(2, 16, i, i, 5, 16);
        check(!s.advance(16.03) && s.x == 299 && s.down, "moves coalesced");
        s.cancel();
        s.advance(17);
        s.accept(3, 17, 299, 299, 5, 17);
        check(!s.advance(17.03) && !s.down && !s.owned, "cancelled gesture cannot commit");
        System.out.println("Touch ordered edges, cancellation, stale UP, timeout and bounds passed");
    }
}
