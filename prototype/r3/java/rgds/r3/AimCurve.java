package rgds.r3;

import com.badlogic.gdx.math.Bezier;
import com.badlogic.gdx.math.Vector2;

/** Shared virtual coordinates: upper 0..768, bezel 768..816, lower 816..1584. */
public final class AimCurve {
    private final Vector2 start = new Vector2(), control = new Vector2();
    private final Vector2 end = new Vector2(), scratch = new Vector2();

    public void set(float x0, float y0, float x1, float y1) {
        start.set(x0, y0);
        end.set(x1, y1);
        // AbstractPlayer's native control point, converted to downward Y.
        control.set(x0 - (x1 - x0) / 4, y1 + (y1 - y0) / 2);
    }

    public void point(Vector2 out, float t) {
        Bezier.quadratic(out, t, start, control, end, scratch);
    }

    public float arrowAngle() {
        return angle(1);
    }

    public float angle(float t) {
        float dx = (1 - t) * (control.x - start.x) + t * (end.x - control.x);
        float dy = (1 - t) * (control.y - start.y) + t * (end.y - control.y);
        return (float)Math.toDegrees(Math.atan2(-dy, dx)) - 90;
    }

    public static int segments(float length, float scale) {
        return Math.max(20, Math.min(96, (int)Math.ceil(length / (48 * scale))));
    }

    public static float bodyScale(float t, float scale) {
        return (7.4f + 8 * t) * scale / 18;
    }

    public static float panelY(float virtualY, int target) {
        return 768 - virtualY + (target == 0 ? 0 : 816);
    }
}
