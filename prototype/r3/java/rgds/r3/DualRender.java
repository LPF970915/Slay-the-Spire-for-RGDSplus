package rgds.r3;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.GL20;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.badlogic.gdx.graphics.g2d.TextureRegion;
import com.badlogic.gdx.math.Matrix4;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.helpers.ImageMaster;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;

/** One native update and one render per gameplay object, two routed viewports. */
public final class DualRender {
    public static final float HAND_SCALE = 1.10f;
    public static final float HAND_RISE = 250f;
    private static final ArrayDeque<State> stack = new ArrayDeque<State>();
    private static final Map<String, Field> fields = new HashMap<String, Field>();
    private static int screen;
    private static int frames, updates;
    private static long nextReport;
    private static Method atlasDraw;
    private static boolean active;
    private static boolean splitDungeon;
    private static final Matrix4 baseProjection = new Matrix4();

    private static final class State {
        final int screen;
        final Matrix4 transform;
        final Matrix4 projection;
        State(SpriteBatch batch) {
            screen = DualRender.screen;
            transform = new Matrix4(batch.getTransformMatrix());
            projection = new Matrix4(batch.getProjectionMatrix());
        }
    }

    public static Object get(Object owner, String name) {
        if (owner == null) return null;
        Class<?> type = owner instanceof Class ? (Class<?>)owner : owner.getClass();
        String key = type.getName() + "." + name;
        try {
            Field field = fields.get(key);
            if (field == null) {
                Class<?> search = type;
                while (search != null) {
                    try { field = search.getDeclaredField(name); break; }
                    catch (NoSuchFieldException missing) { search = search.getSuperclass(); }
                }
                if (field == null) return null;
                field.setAccessible(true);
                fields.put(key, field);
            }
            return field.get(owner instanceof Class ? null : owner);
        } catch (ReflectiveOperationException error) {
            throw new IllegalStateException(error);
        }
    }

    private static void viewport(SpriteBatch batch, int target) {
        batch.flush();
        screen = target;
        Gdx.gl.glViewport(target * 1024, 0, 1024, 768);
    }

    public static void push(SpriteBatch batch, int target, boolean hand) {
        if (!active) return;
        stack.push(new State(batch));
        if (CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY && !splitDungeon)
            target = 1;
        viewport(batch, target);
        Matrix4 transform = new Matrix4();
        if (hand && splitDungeon && !AbstractDungeon.isScreenUp)
            transform.translate(512f, HAND_RISE, 0f)
                .scale(HAND_SCALE, HAND_SCALE, 1f).translate(-512f, 0f, 0f);
        // FontHelper rewrites the transform for rotated card text. Keep the
        // outer layout in projection space so every card sublayer agrees.
        batch.setProjectionMatrix(new Matrix4(baseProjection).mul(transform));
        batch.setTransformMatrix(new Matrix4());
    }

    public static void pop(SpriteBatch batch) {
        if (!active) return;
        State state = stack.pop();
        viewport(batch, state.screen);
        batch.setProjectionMatrix(state.projection);
        batch.setTransformMatrix(state.transform);
    }

    public static void logicTick() { updates++; }

    public static void begin(SpriteBatch batch) {
        if (!stack.isEmpty()) throw new IllegalStateException("Unbalanced dual render scope");
        active = true;
        frames++;
        baseProjection.set(batch.getProjectionMatrix());
        boolean dungeon = CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                CardCrawlGame.dungeon != null && CardCrawlGame.dungeonTransitionScreen == null;
        String room = dungeon && AbstractDungeon.getCurrRoom() != null
                ? AbstractDungeon.getCurrRoom().getClass().getSimpleName() : "";
        splitDungeon = dungeon && room.startsWith("MonsterRoom");
        viewport(batch, splitDungeon ? 0 : 1);
        Color color = new Color(batch.getColor());
        push(batch, 1, false);
        batch.setColor(Color.WHITE);
        if (splitDungeon && AbstractDungeon.scene != null) {
            Object scene = AbstractDungeon.scene;
            Object region = get(scene, "bg");
            if (region instanceof TextureRegion) {
                try {
                    if (atlasDraw == null) {
                        atlasDraw = Class.forName("com.megacrit.cardcrawl.scenes.AbstractScene")
                                .getDeclaredMethod("renderAtlasRegionIf", SpriteBatch.class,
                                    Class.forName("com.badlogic.gdx.graphics.g2d.TextureAtlas$AtlasRegion"),
                                    boolean.class);
                        atlasDraw.setAccessible(true);
                    }
                    atlasDraw.invoke(scene, batch, region, true);
                } catch (ReflectiveOperationException error) {
                    throw new IllegalStateException("Native background layer unavailable", error);
                }
            }
        } else if (!dungeon && CardCrawlGame.mainMenuScreen != null) {
            Object bg = get(CardCrawlGame.mainMenuScreen, "bg");
            Object sky = get(bg, "sky");
            if (sky instanceof TextureRegion)
                batch.draw((TextureRegion)sky, 0, 0, 1024, 768);
        }
        pop(batch);
        batch.setColor(color);
    }

    public static void fadeLower(SpriteBatch batch) {
        Object value = get(CardCrawlGame.class, "screenColor");
        if (!(value instanceof Color)) return;
        Color previous = new Color(batch.getColor());
        push(batch, 1, false);
        batch.setColor((Color)value);
        batch.draw(ImageMaster.WHITE_SQUARE_IMG, 0, 0, 1024, 768);
        pop(batch);
        batch.setColor(previous);
    }

    public static void targeting(SpriteBatch batch, AbstractPlayer player) {
        Object monster = get(player, "hoveredMonster");
        Object card = get(player, "hoveredCard");
        Object hb = get(monster, "hb");
        if (hb == null || card == null) return;
        float tx = ((Number)get(hb, "cX")).floatValue();
        float ty = ((Number)get(hb, "cY")).floatValue();
        float cx = ((Number)get(card, "current_x")).floatValue();
        float cy = ((Number)get(card, "current_y")).floatValue();
        float startX = 512 + (cx - 512) * HAND_SCALE;
        float startY = 816 + 768 - (cy * HAND_SCALE + HAND_RISE);
        float endY = 768 - ty;
        Color color = new Color(batch.getColor());
        for (int target = 0; target < 2; target++) {
            push(batch, target, false);
            batch.setColor(Settings.GOLD_COLOR);
            float distance = (float)Math.hypot(tx-startX, endY-startY);
            for (float d=0; d<distance; d+=22f) {
                float a=d/distance, b=Math.min(d+12f, distance)/distance;
                float x1=startX+(tx-startX)*a, vy1=startY+(endY-startY)*a;
                float x2=startX+(tx-startX)*b, vy2=startY+(endY-startY)*b;
                float offset=target == 0 ? 0 : 816;
                if (vy1 < offset || vy1 > offset+768 || vy2 < offset || vy2 > offset+768) continue;
                float y1=768-(vy1-offset), y2=768-(vy2-offset);
                float length=(float)Math.hypot(x2-x1,y2-y1);
                float angle=(float)Math.toDegrees(Math.atan2(y2-y1,x2-x1));
                batch.draw(ImageMaster.WHITE_SQUARE_IMG, x1, y1-1.5f, 0, 1.5f,
                           length, 3f, 1, 1, angle, 0, 0, 1, 1, false, false);
            }
            if (target == 0) {
                float angle=(float)Math.toDegrees(Math.atan2(startY-endY, tx-startX))-90f;
                batch.draw(ImageMaster.TARGET_UI_ARROW, tx-16, ty-16, 16, 16,
                           32, 32, 1, 1, angle, 0, 0,
                           ImageMaster.TARGET_UI_ARROW.getWidth(),
                           ImageMaster.TARGET_UI_ARROW.getHeight(), false, false);
            }
            pop(batch);
        }
        batch.setColor(color);
    }

    public static void finish(SpriteBatch batch) {
        if (!stack.isEmpty()) throw new IllegalStateException("Unbalanced dual scopes at frame end");
        long now = System.nanoTime();
        if (now >= nextReport) {
            System.out.println("[rgds-r3] frames=" + frames + " updates=" + updates +
                    " logical=" + Settings.WIDTH + "x" + Settings.HEIGHT +
                    " nativeUI=true touchPolicy=capture-only");
            String directory = System.getenv("RGDS_DIAGNOSTICS_DIR");
            if (directory != null) {
                try {
                    Properties state = new Properties();
                    state.setProperty("frames", String.valueOf(frames));
                    state.setProperty("updates", String.valueOf(updates));
                    state.setProperty("nativeUI", "true");
                    state.setProperty("touchPolicy", "capture-only");
                    state.setProperty("handScale", String.valueOf(HAND_SCALE));
                    state.setProperty("handRise", String.valueOf(HAND_RISE));
                    state.setProperty("mode", String.valueOf(CardCrawlGame.mode));
                    state.setProperty("screen", String.valueOf(AbstractDungeon.screen));
                    state.setProperty("layout", splitDungeon ? "battle-split" : "menu-or-full-lower-fallback");
                    Path path = Path.of(directory, "dual-state.xml");
                    Path temp = Path.of(directory, "dual-state.xml.tmp");
                    try (java.io.OutputStream stream=Files.newOutputStream(temp)) {
                        state.storeToXML(stream, "Native dual UI, no physical acceptance claim");
                    }
                    Files.move(temp, path, StandardCopyOption.REPLACE_EXISTING);
                } catch (Exception error) { throw new IllegalStateException(error); }
            }
            nextReport = now + 5_000_000_000L;
        }
        active = false;
    }
}
