import rgds.r3.DragAim;
import java.util.Random;

public final class DragAimTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static int move(DragAim aim, float x, float y, float[][] boxes, int previous) {
        return aim.update(x, y, x, 816 + y, boxes, boxes.length, previous);
    }

    public static void main(String[] args) {
        float[][] boxes = {{800, 300}, {200, 300}, {500, 300}};
        DragAim aim = new DragAim();
        aim.begin(500, 600);
        int selected = move(aim, 500, 580, boxes, -1);
        check(selected == -1 && !aim.active, "Tap/jitter must not arm");
        selected = move(aim, 500, 576, boxes, selected);
        check(selected == 2 && aim.active, "Small upward drag locks nearest target");
        for (int y = 575; y >= 3; y--) {
            selected = move(aim, 500, y, boxes, selected);
            check(selected == 2, "Vertical motion must never unlock or switch");
            check(aim.canRelease(500, y), "Above-hand release after activation");
        }
        check(move(aim, 560, 70, boxes, selected) == 2, "Horizontal dead band");
        selected = move(aim, 564, 70, boxes, selected);
        check(selected == 0, "Right neighbour uses screen order, not list order");
        for (int i = 0; i < 50; i++)
            check(move(aim, 564, 70, boxes, selected) == 0, "Holding never cycles");
        selected = move(aim, 436, 70, boxes, selected);
        check(selected == 1, "Large left swipe traverses neighbours in one update");
        check(move(aim, 436, 599, boxes, selected) == 1, "Hysteresis above original hand");
        check(!aim.canRelease(1, 70) && !aim.canRelease(500, 1), "Slide-off guard");
        selected = move(aim, 436, 600, boxes, selected);
        check(selected == -1 && !aim.active && !aim.canRelease(436, 600), "Return disarms");
        check(move(aim, 800, 740, boxes, selected) == -1, "Free drag below hand");
        selected = move(aim, 800, 576, boxes, -1);
        check(selected == 0 && aim.active, "Same contact can lift again and reacquire");
        check(move(aim, 800, 500, boxes, -1) == -1, "Missing target is never replaced");
        aim.clear();
        check(!aim.canRelease(500, 70), "Cancel clears release eligibility");

        float[][] overlap = {{500, 300}, {500, 300}, {500, 250}};
        aim.begin(500, 600);
        selected = move(aim, 500, 550, overlap, -1);
        check(selected == 0, "Nearest ties use stable source order");
        selected = move(aim, 564, 550, overlap, selected);
        check(selected == 1, "Exactly overlapping targets remain reachable");
        selected = move(aim, 436, 550, overlap, selected);
        check(selected == 2, "Same-column targets use stable Y then source order");

        aim.begin(100, 600);
        check(move(aim, 100, 550, new float[0][0], -1) == -1 && aim.active,
                "No-target cards still enter release region without invented enemy");

        // Grabbing different points on the card preserves the same displaced-card threshold.
        for (int grabOffset : new int[]{-80, 0, 80}) {
            aim.begin(500, 600 + grabOffset);
            check(aim.update(500, 576 + grabOffset, 500, 1392, boxes, 3, -1) == 2,
                    "Grab offset invariant");
        }
        Random rng = new Random(421);
        for (int trial = 0; trial < 2000; trial++) {
            int count = 1 + rng.nextInt(5);
            float[][] targets = new float[count][2];
            for (float[] target : targets) {
                target[0] = 30 + rng.nextInt(965);
                target[1] = 40 + rng.nextInt(650);
            }
            float x = 10 + rng.nextInt(1005), y = 500 + rng.nextInt(240);
            aim.begin(x, y);
            selected = move(aim, x, y - DragAim.ACTIVATE, targets, -1);
            check(selected >= 0 && selected < count, "Initial target always valid");
            for (int i = 0; i < 20; i++) {
                int next = move(aim, x, 3 + rng.nextInt((int)y - 3), targets, selected);
                check(next == selected, "Vertical fuzz must preserve identity");
            }
            check(move(aim, x, y, targets, selected) == -1 && !aim.active, "Fuzz return");
        }
        System.out.println("R4 sticky drag: activation, return/rearm, horizontal ordering, overlap, " +
                "release guards and 2000 vertical-invariance paths passed (not physical touch)");
    }
}
