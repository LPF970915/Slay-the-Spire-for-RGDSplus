package rgds.r3;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Fixed lower-panel keyboard geometry and same-contact release selection. */
public final class KeyboardModel {
    public static final class Key {
        public final String value;
        public final int row, column, span;
        Key(String value, int row, int column, int span) {
            this.value = value; this.row = row; this.column = column; this.span = span;
        }
        public float x() { return 42 + column * 94; }
        public float y() { return 226 + row * 76; }
        public float width() { return span * 94 - 8; }
        public boolean contains(float x, float y) {
            return x >= x() && x < x() + width() && y >= y() && y < y() + 66;
        }
    }

    public final List<Key> keys;
    public int focus;
    public boolean upper;
    private int pressed = -1;

    public KeyboardModel() {
        List<Key> list = new ArrayList<>();
        String[] rows = {"1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm_.'"};
        for (int r = 0; r < rows.length; r++)
            for (int c = 0; c < rows[r].length(); c++)
                list.add(new Key(rows[r].substring(c, c + 1), r, c, 1));
        list.add(new Key("shift", 4, 0, 2));
        list.add(new Key("space", 4, 2, 4));
        list.add(new Key("back", 4, 6, 2));
        list.add(new Key("clear", 4, 8, 2));
        list.add(new Key("cancel", 5, 0, 5));
        list.add(new Key("confirm", 5, 5, 5));
        keys = Collections.unmodifiableList(list);
    }

    public int at(float x, float y) {
        for (int i = 0; i < keys.size(); i++)
            if (keys.get(i).contains(x, y)) return i;
        return -1;
    }

    public void down(float x, float y) {
        pressed = at(x, y);
        if (pressed >= 0) focus = pressed;
    }

    public void move(float excursion) { if (excursion > 12) cancel(); }
    public void cancel() { pressed = -1; }

    public int release(float x, float y, float excursion) {
        move(excursion);
        int result = pressed >= 0 && at(x, y) == pressed ? pressed : -1;
        cancel();
        return result;
    }

    public void navigate(int dx, int dy) {
        Key current = keys.get(focus);
        float center = current.column + current.span / 2f;
        int row = Math.max(0, Math.min(5, current.row + dy));
        float best = Float.MAX_VALUE;
        int found = focus;
        for (int i = 0; i < keys.size(); i++) {
            Key key = keys.get(i);
            if (key.row != row) continue;
            float delta = key.column + key.span / 2f - center;
            if (dy == 0 && (dx < 0 && delta >= 0 || dx > 0 && delta <= 0)) continue;
            if (Math.abs(delta) < best) { best = Math.abs(delta); found = i; }
        }
        focus = found;
    }

    public static String backspace(String text) {
        return text.isEmpty() ? text : text.substring(0, text.offsetByCodePoints(text.length(), -1));
    }

    public static String appendName(String text, char value) {
        if (text.codePointCount(0, text.length()) >= 24) return text;
        return value >= ' ' && value <= '~' &&
                (Character.isLetterOrDigit(value) || " -_.'".indexOf(value) >= 0)
                ? text + value : text;
    }
}
