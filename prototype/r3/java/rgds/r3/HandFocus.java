package rgds.r3;

/** Enter each room without carrying a controller selection from the previous screen. */
public final class HandFocus {
    private Object room;
    private long padVersion;
    private boolean neutral = true;
    private boolean interactive;

    public boolean neutral(Object currentRoom, long currentPadVersion) {
        return neutral(currentRoom, currentPadVersion, true);
    }

    public boolean neutral(Object currentRoom, long currentPadVersion, boolean canSelectHand) {
        if (room != currentRoom || !canSelectHand || !interactive) {
            room = currentRoom;
            padVersion = currentPadVersion;
            neutral = true;
        } else if (padVersion != currentPadVersion) {
            padVersion = currentPadVersion;
            neutral = false;
        }
        interactive = canSelectHand;
        return neutral;
    }
}
