package rgds.r3;

import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.BitmapFont;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.FontHelper;
import com.megacrit.cardcrawl.helpers.ImageMaster;
import com.megacrit.cardcrawl.screens.custom.CustomMod;
import com.megacrit.cardcrawl.screens.custom.CustomModeCharacterButton;
import com.megacrit.cardcrawl.screens.mainMenu.SaveSlot;
import com.megacrit.cardcrawl.rewards.RewardItem;
import java.util.ArrayList;
import java.util.List;

/** Read-only summaries from the current native model, without new game objects. */
public final class PageSummary {
    private static final List<String> lines = new ArrayList<String>();

    public static void render(SpriteBatch batch, String page) {
        if (CardCrawlGame.cardPopup.isOpen || CardCrawlGame.relicPopup.isOpen) return;
        Object fade = DualRender.get(CardCrawlGame.class, "screenColor");
        if (fade instanceof Color && ((Color)fade).a > .1f) return;
        lines.clear();
        if (page.equals("U03")) {
            for (SaveSlot slot : CardCrawlGame.mainMenuScreen.saveSlotScreen.slots)
                if (!slot.emptySlot) lines.add(slot.getName());
        } else if (page.equals("U05")) {
            for (CustomModeCharacterButton c : CardCrawlGame.mainMenuScreen.customModeScreen.options)
                if (c.selected) lines.add(c.c.getTitle(c.c.chosenClass));
            Object mods = DualRender.get(CardCrawlGame.mainMenuScreen.customModeScreen, "modList");
            if (mods instanceof Iterable)
                for (Object value : (Iterable<?>)mods) {
                    CustomMod mod = (CustomMod)value;
                    if (mod.selected) lines.add(mod.name);
                }
        } else if (page.equals("U17")) {
            for (RewardItem reward : AbstractDungeon.combatRewardScreen.rewards)
                if (!reward.isDone && !reward.ignoreReward) lines.add(reward.text);
        } else if (page.equals("U22")) {
            Object ui = DualRender.get(AbstractDungeon.getCurrRoom(), "campfireUI");
            Object buttons = DualRender.get(ui, "buttons");
            if (buttons instanceof Iterable)
                for (Object value : (Iterable<?>)buttons) {
                    Object hb = DualRender.get(value, "hb");
                    if (hb instanceof com.megacrit.cardcrawl.helpers.Hitbox &&
                            ((com.megacrit.cardcrawl.helpers.Hitbox)hb).hovered) {
                        lines.add(String.valueOf(DualRender.get(value, "label")));
                        lines.add(String.valueOf(DualRender.get(value, "description")));
                        break;
                    }
                }
        }
        if (lines.isEmpty()) return;
        Color old = new Color(batch.getColor());
        BitmapFont font = FontHelper.panelNameFont;
        float sx = font.getData().scaleX, sy = font.getData().scaleY;
        Color fontColor = new Color(font.getColor());
        DualRender.push(batch, 0, false);
        try {
            batch.setColor(.035f, .045f, .05f, .82f);
            float height = Math.min(420, 64 + lines.size() * 64);
            batch.draw(ImageMaster.WHITE_SQUARE_IMG, 32, 680 - height, 960, height);
            font.getData().setScale(sx * 1.4f, sy * 1.4f);
            float y = 624;
            for (String text : lines) {
                if (text == null || text.isEmpty() || y < 160) continue;
                FontHelper.renderSmartText(batch, font, text, 80, y, 864, 36, Color.WHITE);
                y -= Math.max(56, Math.abs(FontHelper.getSmartHeight(font, text, 864, 36)) + 24);
            }
        } finally {
            font.getData().setScale(sx, sy);
            font.setColor(fontColor);
            DualRender.pop(batch);
            batch.setColor(old);
        }
    }
}
