import rgds.r3.MapGesture;
import rgds.r3.TouchState;

public final class MapGestureTest {
    private static void check(boolean ok) { if (!ok) throw new AssertionError(); }
    public static void main(String[] args) {
        Object node = new Object(), other = new Object();
        MapGesture g = new MapGesture();
        g.begin(400, 400, 0, node, true);
        g.move(405, 403, 6, -500, 100);
        check(g.release(node, 405, 403));
        check(!g.release(node, 405, 403));
        g.begin(400, 400, 0, node, true);
        check(g.move(400, 500, 100, -500, 100) == -100);
        g.move(400, 400, 100, -500, 100);
        check(!g.release(node, 400, 400));
        g.begin(400, 400, 0, node, true);
        g.move(500, 400, 100, -500, 100);
        check(!g.release(other, 500, 400));
        g.begin(400, 400, 0, node, true);
        check(!g.release(other, 400, 400));
        g.begin(400, 400, 0, node, true);
        g.cancel();
        check(!g.release(node, 400, 400));
        g.begin(400, 400, 0, node, false);
        check(g.move(400, 700, 300, -500, 100) == 0);
        check(!g.release(node, 400, 700));
        g.begin(400, 400, 0, null, true);
        check(g.move(400, 0, 400, -500, 100) == 100);
        check(g.move(400, 10, 400, -500, 100) == 90);
        check(g.move(400, 768, 768, -500, 100) == -500);
        check(!g.release(node, 400, 768));
        g.begin(400, 400, 0, node, true);
        g.move(400, 400, 40, -500, 100);
        check(!g.release(node, 400, 400));
        TouchState s = new TouchState();
        s.accept(TouchState.DOWN, 1, 400, 400, 1, 1);
        s.accept(TouchState.MOVE, 1, 400, 500, 1, 1);
        s.accept(TouchState.MOVE, 1, 400, 400, 1, 1);
        s.accept(TouchState.UP, 1, 400, 400, 1, 1);
        s.advance(1); check(s.justDown && s.excursion == 0);
        s.advance(1); check(s.y == 400 && s.excursion == 100);
        s.advance(1); check(s.justUp && s.excursion == 100);
        s.cancel(); check(s.excursion == 0);
        System.out.println("Map tap/drag: sticky slop, same target, boundaries, HUD, cancel and coalesced excursion passed");
    }
}
