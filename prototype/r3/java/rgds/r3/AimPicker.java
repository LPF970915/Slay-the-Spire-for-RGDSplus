package rgds.r3;

/** Direction sectors from P1 geometry; coordinates include the 48px bezel. */
public final class AimPicker {
    public static int pick(float ox, float oy, float px, float py,
                           float[][] boxes, int count, int previous) {
        if (oy - py < 48) return -1;
        double angle = Math.atan2(px - ox, oy - py);
        int direct = -1, hits = 0, best = -1;
        double bestCenter = Double.POSITIVE_INFINITY, second = bestCenter;
        double bestDistance = bestCenter, oldCenter = bestCenter, oldDistance = bestCenter;
        for (int i = 0; i < count; i++) {
            float[] box = boxes[i];
            double lo = Double.POSITIVE_INFINITY, hi = Double.NEGATIVE_INFINITY;
            for (int x = -1; x <= 1; x += 2) {
                for (int y = -1; y <= 1; y += 2) {
                    double corner = Math.atan2(box[0] + x * box[2] / 2 - ox,
                                              oy - box[1] - y * box[3] / 2);
                    lo = Math.min(lo, corner); hi = Math.max(hi, corner);
                }
            }
            double distance = Math.max(Math.max(lo - angle, angle - hi), 0);
            double center = Math.abs(angle - Math.atan2(box[0] - ox, oy - box[1]));
            if (distance == 0) { direct = i; hits++; }
            if (center < bestCenter) {
                second = bestCenter; bestCenter = center; bestDistance = distance; best = i;
            } else second = Math.min(second, center);
            if (i == previous) { oldCenter = center; oldDistance = distance; }
        }
        if (hits > 1) return -1;
        if (hits == 1) return direct;
        if (best < 0 || bestDistance > .14) return -1;
        if (oldDistance <= .14 && oldCenter <= bestCenter + .035) return previous;
        if (second - bestCenter < .002) return -1;
        return best;
    }
}
