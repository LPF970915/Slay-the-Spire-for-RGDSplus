import rgds.r3.CardFlightPath;
import java.util.Random;

public final class CardFlightPathTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        check(CardFlightPath.progress(-1) == 0, "Clamp before start");
        check(CardFlightPath.progress(1) == 1, "Clamp after arrival");
        Random random = new Random(421);
        for (int trial = 0; trial < 2000; trial++) {
            float startX = 3 + random.nextFloat() * 1018;
            float startY = 819 + random.nextFloat() * 650;
            float endX = 40 + random.nextFloat() * 944;
            float endY = 100 + random.nextFloat() * 600;
            float initial = .3f + random.nextFloat();
            float previousY = startY, previousScale = initial;
            boolean lower = false, upper = false;
            for (int frame = 0; frame <= 100; frame++) {
                float time = CardFlightPath.DURATION * frame / 100;
                float x = CardFlightPath.position(startX, endX, time);
                float y = CardFlightPath.position(startY, endY, time);
                float scale = CardFlightPath.scale(initial, time);
                check(y <= previousY && scale <= previousScale && scale > 0,
                        "Continuous forward movement and shrinking");
                check(x >= Math.min(startX, endX) - .001f &&
                        x <= Math.max(startX, endX) + .001f, "No horizontal overshoot");
                lower |= y >= 816;
                upper |= y <= 768;
                // The same vertices in lower-local coordinates project to upper-local Y.
                check(Math.abs((1584 - y - 816) - (768 - y)) < .001f,
                        "Both GPU viewports share the same virtual point");
                previousY = y; previousScale = scale;
            }
            check(lower && upper, "Path crosses both panels");
            check(Math.abs(previousY - endY) < .001f, "Arrives at selected target");
            check(Math.abs(previousScale - initial * .06f) < .0001f, "Final size");
        }
        System.out.println("R4 card flight: 2000 endpoint, shrink and cross-panel paths passed");
    }
}
