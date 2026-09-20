import rgds.r3.UiTransform;

public final class UiTransformTest {
    private static void close(float actual, float expected) {
        if (Math.abs(actual - expected) > 0.001f)
            throw new AssertionError(actual + " != " + expected);
    }

    public static void main(String[] args) {
        int samples = 0;
        for (int count = 0; count <= 10; count++) {
            UiTransform layout = UiTransform.hand(count);
            close(layout.x(512), 512);
            close(layout.y(0), 315);
            for (float x : new float[]{0, 16, 256, 512, 768, 1008, 1024}) {
                for (float y : new float[]{0, 16, 192, 384, 576, 752, 768}) {
                    close(layout.inverseX(layout.x(x)), x);
                    close(layout.inverseY(layout.y(y)), y);
                    samples++;
                }
            }
        }
        UiTransform pile = UiTransform.anchored(1.4f, 44, 40, 68, 62);
        close(pile.x(44), 68);
        close(pile.y(40), 62);
        if (!(UiTransform.hand(5).scale > UiTransform.hand(8).scale))
            throw new AssertionError("Crowded hands must use a bounded smaller scale");
        System.out.println("R3 affine round trips passed: " + samples +
                " points; anchors and crowded-hand scaling passed (not physical touch)");
    }
}
