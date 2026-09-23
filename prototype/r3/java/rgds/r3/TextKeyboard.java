package rgds.r3;

import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.BitmapFont;
import com.badlogic.gdx.graphics.g2d.GlyphLayout;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.helpers.FontHelper;
import com.megacrit.cardcrawl.helpers.ImageMaster;
import com.megacrit.cardcrawl.helpers.SeedHelper;
import com.megacrit.cardcrawl.helpers.controller.CInputAction;
import com.megacrit.cardcrawl.helpers.controller.CInputActionSet;
import com.megacrit.cardcrawl.helpers.input.InputHelper;
import com.megacrit.cardcrawl.ui.panels.RenamePopup;
import com.megacrit.cardcrawl.ui.panels.SeedPanel;

/** Edits native text fields; only native confirm/cancel may persist a value. */
public final class TextKeyboard {
    private static Object owner;
    private static KeyboardModel model;
    private static int heldKeys;
    private static long epoch;
    private static final int[] KEYS = {19, 20, 21, 22, 62, 131, 52, 66, 41, 61};
    private static final GlyphLayout glyph = new GlyphLayout();

    public static boolean active() { return owner != null; }
    public static long epoch() { return epoch; }
    public static boolean owns(Object value) { return value == owner; }

    private static int keys() {
        int value = 0;
        for (int i = 0; i < KEYS.length; i++)
            if (rgds.InputEdges.pressed(KEYS[i])) value |= 1 << i;
        return value;
    }

    public static void open(Object value) {
        if (!TouchInput.enabled) return;
        owner = value;
        model = new KeyboardModel();
        model.upper = value instanceof SeedPanel;
        heldKeys = keys();
        epoch++;
        TouchInput.state.cancel();
        DualRender.cancelTouchHits();
        consume();
    }

    public static void closed(Object value) {
        if (owner != value) return;
        owner = null;
        epoch++;
        TouchInput.state.cancel();
        DualRender.cancelTouchHits();
        consume();
    }

    public static void cancelContact() { if (model != null) model.cancel(); }

    private static String text() {
        return owner instanceof SeedPanel ? SeedPanel.textField : RenamePopup.textField;
    }

    private static void text(String value) {
        if (owner instanceof SeedPanel) SeedPanel.textField = value;
        else RenamePopup.textField = value;
    }

    public static void consume() {
        InputHelper.justClickedLeft = InputHelper.justReleasedClickLeft = false;
        InputHelper.touchDown = InputHelper.touchUp = InputHelper.pressedEscape = false;
        CInputAction[] actions = {CInputActionSet.select, CInputActionSet.cancel,
                CInputActionSet.proceed, CInputActionSet.topPanel, CInputActionSet.settings,
                CInputActionSet.map, CInputActionSet.up, CInputActionSet.down,
                CInputActionSet.left, CInputActionSet.right, CInputActionSet.altUp,
                CInputActionSet.altDown, CInputActionSet.altLeft, CInputActionSet.altRight};
        for (CInputAction action : actions) if (action != null) action.unpress();
    }

    public static boolean update(Object value) {
        if (owner != value) return false;
        int now = keys(), edges = now & ~heldKeys;
        heldKeys = now;
        TouchState touch = TouchInput.state;
        // Cancel has priority over a simultaneous touch release or confirmation.
        if ((edges & (1 << 5)) != 0) activate("cancel");
        else if ((edges & (1 << 7)) != 0) activate("confirm");
        else if ((edges & (1 << 6)) != 0) activate("back");
        else if (edges != 0) {
            model.cancel();
            if ((edges & 1) != 0) model.navigate(0, -1);
            else if ((edges & 2) != 0) model.navigate(0, 1);
            else if ((edges & 4) != 0) model.navigate(-1, 0);
            else if ((edges & 8) != 0) model.navigate(1, 0);
            else if ((edges & 16) != 0) activate(model.keys.get(model.focus).value);
        } else if (TouchInput.ownsPointer()) {
            if (touch.justDown) model.down(touch.x, touch.y);
            model.move(touch.excursion);
            if (touch.justUp) {
                int key = model.release(touch.x, touch.y, touch.excursion);
                if (key >= 0) activate(model.keys.get(key).value);
            }
        }
        consume();
        return true;
    }

    private static void activate(String key) {
        if (owner == null) return;
        if (key.equals("cancel")) {
            if (owner instanceof SeedPanel) ((SeedPanel)owner).cancel();
            else ((RenamePopup)owner).cancel();
        } else if (key.equals("confirm")) {
            if (owner instanceof SeedPanel) ((SeedPanel)owner).confirm();
            else if (!text().trim().isEmpty()) ((RenamePopup)owner).confirm();
        } else if (key.equals("clear")) text("");
        else if (key.equals("back")) text(KeyboardModel.backspace(text()));
        else if (key.equals("shift")) {
            if (!(owner instanceof SeedPanel)) model.upper = !model.upper;
        } else {
            char c = key.equals("space") ? ' ' : key.charAt(0);
            if (model.upper) c = Character.toUpperCase(c);
            if (owner instanceof SeedPanel) {
                if (!SeedPanel.isFull()) {
                    String valid = SeedHelper.getValidCharacter(String.valueOf(c), text());
                    if (valid != null) text(text() + valid);
                }
            } else text(KeyboardModel.appendName(text(), c));
        }
    }

    private static String label(String value) {
        boolean cn = Settings.language == Settings.GameLanguage.ZHS || Settings.language == Settings.GameLanguage.ZHT;
        switch (value) {
            case "shift": return model.upper ? "ABC" : "abc";
            case "space": return cn ? "\u7a7a\u683c" : "Space";
            case "back": return cn ? "\u9000\u683c" : "Backspace";
            case "clear": return cn ? "\u6e05\u7a7a" : "Clear";
            case "cancel": return cn ? "\u53d6\u6d88" : "Cancel";
            case "confirm": return cn ? "\u786e\u8ba4" : "Confirm";
            default: return model.upper ? value.toUpperCase(java.util.Locale.ROOT) : value;
        }
    }

    private static void centered(SpriteBatch batch, BitmapFont font, String text,
                                 float x, float y, float width) {
        float sx = font.getData().scaleX, sy = font.getData().scaleY;
        glyph.setText(font, text);
        if (glyph.width > width) font.getData().setScale(sx * width / glyph.width, sy * width / glyph.width);
        glyph.setText(font, text);
        font.draw(batch, text, x - glyph.width / 2, y + glyph.height / 2);
        font.getData().setScale(sx, sy);
    }

    public static void render(SpriteBatch batch) {
        if (!active()) return;
        Color saved = new Color(batch.getColor());
        BitmapFont font = FontHelper.panelNameFont;
        Color color = new Color(font.getColor());
        float sx = font.getData().scaleX, sy = font.getData().scaleY;
        DualRender.push(batch, 1, false);
        try {
            batch.setColor(.045f, .065f, .065f, .99f);
            batch.draw(ImageMaster.WHITE_SQUARE_IMG, 0, 0, 1024, 768);
            boolean cn = Settings.language == Settings.GameLanguage.ZHS || Settings.language == Settings.GameLanguage.ZHT;
            font.getData().setScale(sx * 1.25f, sy * 1.25f);
            font.setColor(Settings.GOLD_COLOR);
            centered(batch, font, owner instanceof SeedPanel ? (cn ? "\u79cd\u5b50" : "Seed") :
                    (cn ? "\u540d\u79f0" : "Name"), 512, 700, 900);
            batch.setColor(.12f, .16f, .17f, 1);
            batch.draw(ImageMaster.WHITE_SQUARE_IMG, 42, 590, 932, 76);
            font.setColor(Color.WHITE);
            centered(batch, font, text().isEmpty() ? "|" : text() + "|", 508, 628, 880);
            for (int i = 0; i < model.keys.size(); i++) {
                KeyboardModel.Key key = model.keys.get(i);
                boolean disabled = owner instanceof SeedPanel &&
                        (key.value.equals("space") || key.value.equals("shift") ||
                         key.value.equals("-") || key.value.equals("_") ||
                         key.value.equals(".") || key.value.equals("'"));
                if (i == model.focus) batch.setColor(.52f, .46f, .22f, 1);
                else batch.setColor(.16f, .22f, .23f, 1);
                batch.draw(ImageMaster.WHITE_SQUARE_IMG, key.x(), 768 - key.y() - 66, key.width(), 66);
                font.setColor(disabled ? Color.GRAY : Color.WHITE);
                centered(batch, font, label(key.value), key.x() + key.width() / 2,
                        768 - key.y() - 33, key.width() - 18);
            }
        } finally {
            font.getData().setScale(sx, sy);
            font.setColor(color);
            DualRender.pop(batch);
            batch.setColor(saved);
        }
    }

    public static void diagnostics(java.util.Properties state) {
        state.setProperty("keyboard.open", Boolean.toString(active()));
        if (active()) {
            state.setProperty("keyboard.kind", owner instanceof SeedPanel ? "seed" : "name");
            state.setProperty("keyboard.text", text());
            state.setProperty("keyboard.focus", model.keys.get(model.focus).value);
        }
    }
}
