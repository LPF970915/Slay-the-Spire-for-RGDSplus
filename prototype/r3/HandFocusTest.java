import rgds.r3.HandFocus;

public final class HandFocusTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        HandFocus focus = new HandFocus();
        Object first = new Object(), second = new Object();
        check(focus.neutral(first, 5), "Menu input must not select the first combat card");
        for (int i = 0; i < 1000; i++)
            check(focus.neutral(first, 5), "Idle and held menu keys keep the natural hand");
        check(!focus.neutral(first, 6), "A new combat key restores native selection immediately");
        check(!focus.neutral(first, 6), "Pad selection persists after key release");
        check(focus.neutral(second, 6), "The next battle starts neutral again");
        check(!focus.neutral(second, 7), "Pad can take over in each battle");
        check(focus.neutral(null, 7), "Leaving the room clears old selection ownership");
        check(focus.neutral(first, 8), "Re-entering is not a continuation of old pad selection");
        check(focus.neutral(first, 9, false), "Tutorial keys never take hand ownership");
        check(focus.neutral(first, 10, false), "Repeated tutorial next stays neutral");
        check(focus.neutral(first, 10, true), "Closing tutorial preserves natural fan");
        check(focus.neutral(first, 10, true), "Idle after tutorial does not lift first card");
        check(!focus.neutral(first, 11, true), "Fresh combat key still takes ownership");
        check(focus.neutral(first, 12, false), "No cards or an overlay reset stale selection");
        check(focus.neutral(first, 12, true), "Newly drawn hand enters the fan");
        System.out.println("R4 neutral hand: entry, idle, held keys, pad takeover and new room passed");
    }
}
