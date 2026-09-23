import rgds.r3.KeyboardModel;

public final class KeyboardModelTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        KeyboardModel model = new KeyboardModel();
        for (int i = 0; i < model.keys.size(); i++) {
            KeyboardModel.Key key = model.keys.get(i);
            float x = key.x() + key.width() / 2, y = key.y() + 33;
            check(x > 0 && x < 1024 && y > 0 && y < 768, "visible");
            model.down(x, y);
            check(model.release(x, y, 0) == i, "same-contact key " + i);
            check(model.release(x, y, 0) == -1, "no duplicate release");
            model.down(x, y);
            model.move(24);
            check(model.release(x, y, 0) == -1, "drag back cannot type");
            model.down(x, y);
            model.cancel();
            check(model.release(x, y, 0) == -1, "B/multifinger/context cancel");
            model.focus = i;
            for (int j = 0; j < 8; j++) model.navigate(0, 1);
            check(model.keys.get(model.focus).row == 5, "confirm/cancel reachable from every key");
        }
        model.down(44, 230);
        check(model.release(145, 230, 0) == -1, "different final coordinate");
        check(model.at(0, 0) == -1 && model.at(130, 230) == -1, "gaps are not keys");
        String name = "";
        for (char c : "Test 09-a_B.c'".toCharArray()) name = KeyboardModel.appendName(name, c);
        check(name.equals("Test 09-a_B.c'"), "letters digits spaces punctuation");
        check(KeyboardModel.appendName(name, '\n').equals(name), "control rejected");
        check(KeyboardModel.appendName(name, '/').equals(name), "path punctuation rejected");
        for (int i = 0; i < 100; i++) name = KeyboardModel.appendName(name, 'A');
        check(name.length() == 24, "bounded name");
        check(KeyboardModel.backspace("").isEmpty(), "empty backspace");
        check(KeyboardModel.backspace("a\uD83D\uDE00").equals("a"), "codepoint backspace");
        System.out.println("Keyboard geometry, navigation, editing and release ownership passed");
    }
}
