import java.util.Scanner;
import rgds.r3.AimPicker;

/** Consume P1-generated vectors to prevent independent geometry policy drift. */
public final class AimPickerTest {
    public static void main(String[] args) {
        Scanner input = new Scanner(System.in).useLocale(java.util.Locale.ROOT);
        int cases = input.nextInt();
        for (int n = 0; n < cases; n++) {
            float ox = input.nextFloat(), oy = input.nextFloat();
            float px = input.nextFloat(), py = input.nextFloat();
            int previous = input.nextInt(), expected = input.nextInt(), count = input.nextInt();
            float[][] boxes = new float[count][4];
            for (float[] box : boxes)
                for (int i = 0; i < 4; i++) box[i] = input.nextFloat();
            int actual = AimPicker.pick(ox, oy, px, py, boxes, count, previous);
            if (actual != expected)
                throw new AssertionError("P1 vector " + n + ": " + actual + " != " + expected);
        }
        System.out.println("P1/Java direction geometry agreement: " + cases + " vectors");
    }
}
