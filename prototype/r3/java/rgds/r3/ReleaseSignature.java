package rgds.r3;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.BitmapFont;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.badlogic.gdx.graphics.g2d.freetype.FreeTypeFontGenerator;
import com.badlogic.gdx.graphics.g2d.freetype.FreeTypeFontGenerator.FreeTypeFontParameter;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.helpers.FontHelper;
import com.megacrit.cardcrawl.screens.mainMenu.MainMenuScreen;

/** Lower-screen release credit, matching the Balatro for RGDSplus main-menu badge. */
public final class ReleaseSignature {
    private static final String CREDIT = "移植by Blood_roc";
    private static BitmapFont font;

    private ReleaseSignature() {}

    public static boolean visible() {
        MainMenuScreen menu = CardCrawlGame.mainMenuScreen;
        return CardCrawlGame.mode == CardCrawlGame.GameMode.CHAR_SELECT && menu != null &&
                (menu.screen == MainMenuScreen.CurScreen.MAIN_MENU ||
                        menu.screen == MainMenuScreen.CurScreen.PANEL_MENU);
    }

    public static String versionLine() {
        String version = CardCrawlGame.VERSION_NUM == null ? "" : CardCrawlGame.VERSION_NUM.trim();
        return "Slay the Spire " + version + " for RGDSplus";
    }

    public static void draw(SpriteBatch batch) {
        if (!visible()) return;
        BitmapFont face = font();
        Color previous = face.getColor();
        FontHelper.renderFontRightTopAligned(batch, face, versionLine(), 1004.0f, 748.0f, Color.WHITE);
        FontHelper.renderFontRightTopAligned(batch, face, CREDIT, 1004.0f, 722.0f, Color.WHITE);
        face.setColor(previous);
    }

    private static BitmapFont font() {
        if (font != null) return font;
        // The active menu language may not contain the Chinese credit.
        try {
            FreeTypeFontGenerator generator = new FreeTypeFontGenerator(
                    Gdx.files.internal("font/zhs/NotoSansMonoCJKsc-Regular.otf"));
            try {
                FreeTypeFontParameter parameter = new FreeTypeFontParameter();
                parameter.size = 16;
                parameter.characters = "Slay the SpireV0123456789.-()[] forRGDSplus" + CREDIT;
                parameter.incremental = false;
                font = generator.generateFont(parameter);
            } finally {
                generator.dispose();
            }
        } catch (RuntimeException error) {
            font = FontHelper.tipBodyFont;
        }
        return font;
    }
}
