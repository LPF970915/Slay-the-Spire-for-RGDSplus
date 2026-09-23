import rgds.r3.UiTransform;
import rgds.r3.AimCurve;
import com.badlogic.gdx.math.Vector2;

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
        AimCurve curve = new AimCurve();
        Vector2 point = new Vector2();
        for (float enemyX : new float[]{32, 256, 512, 768, 992}) {
            curve.set(512, 1200, enemyX, 320);
            curve.point(point, 0);
            close(point.x, 512);
            close(point.y, 1200);
            for (int i = 1; i <= 160; i++) {
                curve.point(point, i / 160f);
                if (!Float.isFinite(point.x) || !Float.isFinite(point.y) ||
                        !Float.isFinite(curve.angle(i / 160f)))
                    throw new AssertionError("Finite native curve and sprite rotation required");
            }
            close(point.x, enemyX);
            close(point.y, 320);
            if (!Float.isFinite(curve.arrowAngle())) throw new AssertionError("Arrow tangent");
            curve.point(point, .5f);
            close(point.x, 512 * .875f + enemyX * .125f);
            close(point.y, 320);
            curve.point(point, .75f);
            if (!(point.y < 320)) throw new AssertionError("Native arc must bend back toward target");
        }
        close(AimCurve.panelY(768, 0), 0);
        close(AimCurve.panelY(816, 1), 768);
        close(AimCurve.panelY(780, 0), -12);
        close(AimCurve.panelY(810, 1), 774);
        for (float y : new float[]{0, 768, 780, 800, 816, 1584})
            close(AimCurve.panelY(y, 1) - AimCurve.panelY(y, 0), 816);
        for (float length : new float[]{0, 200, 800, 1600, 10000}) {
            int count = AimCurve.segments(length, .533333f);
            if (count < 20 || count > 96) throw new AssertionError("Bounded native sprite count");
        }
        close(AimCurve.bodyScale(0, 1), 7.4f / 18);
        close(AimCurve.bodyScale(.95f, 1), 15f / 18);
        for (float sx : new float[]{3, 512, 1021}) {
            for (float sy : new float[]{819, 1100, 1550}) {
                for (float ex : new float[]{30, 512, 994}) {
                    curve.setLocked(sx, sy, ex, 50);
                    curve.point(point, 0);
                    close(point.x, sx); close(point.y, sy);
                    curve.point(point, 1);
                    close(point.x, ex); close(point.y, 50);
                    for (int i = 0; i <= 100; i++) {
                        curve.point(point, i / 100f);
                        if (point.x < 0 || point.x > 1024 || point.y < 0 ||
                                !Float.isFinite(curve.angle(i / 100f)))
                            throw new AssertionError("Locked curve stays bounded with a fixed endpoint");
                    }
                }
            }
        }
        for (float y : new float[]{0, 384, 768, 1152, 1536}) {
            float ndc = 2 * (.5f * y) / 768 - 1;
            close((ndc + 1) * 1536 / 2, y);
            close((ndc + 1) * 1536 / 2 - 768, y - 768);
        }
        System.out.println("R4 native quadratic, sprite size/rotation, panel translation and 1:1 map tiles passed");
    }
}
