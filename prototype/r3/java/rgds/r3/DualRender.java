package rgds.r3;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.badlogic.gdx.graphics.g2d.TextureRegion;
import com.badlogic.gdx.math.Matrix4;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.core.AbstractCreature;
import com.megacrit.cardcrawl.monsters.AbstractMonster;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.helpers.ImageMaster;
import com.megacrit.cardcrawl.helpers.Hitbox;
import com.megacrit.cardcrawl.helpers.input.InputHelper;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;
import java.util.WeakHashMap;

/** One native update and one render per gameplay object, two routed viewports. */
public final class DualRender {
    private static final ArrayDeque<State> stack = new ArrayDeque<State>();
    private static final ArrayDeque<State> freeStates = new ArrayDeque<State>();
    private static final Map<String, Field> fields = new HashMap<String, Field>();
    private static int screen;
    private static int frames, updates;
    private static long nextReport;
    private static boolean backgroundPass;
    private static int backgroundBatches;
    private static final Map<Hitbox, UiTransform> hitTransforms = new WeakHashMap<Hitbox, UiTransform>();
    private static final int[][] pointers = new int[32][3];
    private static int pointerDepth;
    private static boolean active;
    private static boolean splitDungeon;
    private static final Matrix4 baseProjection = new Matrix4();
    private static final Matrix4 layoutMatrix = new Matrix4();
    private static final Matrix4 projectedMatrix = new Matrix4();
    private static Object registeredRoom;
    private static Object registeredScreen;

    private static final class State {
        int screen;
        final Matrix4 transform = new Matrix4();
        final Matrix4 projection = new Matrix4();
        void save(SpriteBatch batch) {
            screen = DualRender.screen;
            transform.set(batch.getTransformMatrix());
            projection.set(batch.getProjectionMatrix());
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
        State saved = freeStates.pollFirst();
        if (saved == null) saved = new State();
        saved.save(batch);
        stack.push(saved);
        if (CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY && !splitDungeon)
            target = 1;
        viewport(batch, target);
        Matrix4 transform = layoutMatrix.idt();
        if (hand && splitDungeon && !AbstractDungeon.isScreenUp) {
            UiTransform layout = handLayout();
            transform.translate(layout.dx, layout.dy, 0).scale(layout.scale, layout.scale, 1);
            for (com.megacrit.cardcrawl.cards.AbstractCard card : AbstractDungeon.player.hand.group)
                hitTransforms.put(card.hb, layout);
        }
        // FontHelper rewrites the transform for rotated card text. Keep the
        // outer layout in projection space so every card sublayer agrees.
        batch.setProjectionMatrix(projectedMatrix.set(baseProjection).mul(transform));
        batch.setTransformMatrix(layoutMatrix.idt());
    }

    public static void pop(SpriteBatch batch) {
        if (!active) return;
        State state = stack.pop();
        viewport(batch, state.screen);
        batch.setProjectionMatrix(state.projection);
        batch.setTransformMatrix(state.transform);
        freeStates.addFirst(state);
    }

    public static void logicTick() { updates++; }

    private static UiTransform handLayout() {
        return UiTransform.hand(AbstractDungeon.player == null ? 0 : AbstractDungeon.player.hand.size());
    }

    private static boolean combatLayout() {
        return CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                CardCrawlGame.dungeon != null && AbstractDungeon.getCurrRoom() != null &&
                AbstractDungeon.getCurrRoom().getClass().getSimpleName().startsWith("MonsterRoom");
    }

    public static void pointerBegin(Hitbox hb) {
        if (pointerDepth == pointers.length) throw new IllegalStateException("Nested hitbox overflow");
        int[] saved = pointers[pointerDepth++];
        saved[0] = InputHelper.mX;
        saved[1] = InputHelper.mY;
        saved[2] = 0;
        UiTransform layout = hitTransforms.get(hb);
        if (layout != null && combatLayout() && !AbstractDungeon.isScreenUp &&
                !Settings.isControllerMode) {
            saved[2] = 1;
            InputHelper.mX = Math.round(layout.inverseX(InputHelper.mX));
            InputHelper.mY = Math.round(layout.inverseY(InputHelper.mY));
        }
    }

    public static void pointerEnd() {
        int[] saved = pointers[--pointerDepth];
        if (saved[2] != 0) {
            InputHelper.mX = saved[0];
            InputHelper.mY = saved[1];
        }
    }

    public static void pushControl(SpriteBatch batch, Object owner, String kind) {
        push(batch, 1, false);
        if (!splitDungeon || AbstractDungeon.isScreenUp) return;
        Object value = get(owner, kind.equals("energy") ? "tipHitbox" : "hb");
        if (!(value instanceof Hitbox)) return;
        Hitbox hb = (Hitbox)value;
        float x = hb.cX, y = hb.cY;
        float toX = x, toY = y;
        if (kind.equals("energy")) toY += 24;
        if (kind.equals("draw")) { toX = 68; toY = 62; }
        if (kind.equals("discard")) { toX = 956; toY = 62; }
        float dx = toX - x * 1.40f, dy = toY - y * 1.40f;
        UiTransform layout = hitTransforms.get(hb);
        if (layout == null || layout.scale != 1.40f || layout.dx != dx || layout.dy != dy)
            layout = new UiTransform(1.40f, dx, dy);
        applyLayout(batch, layout);
        hitTransforms.put(hb, layout);
    }

    public static void pushInfo(SpriteBatch batch, Object owner, String kind) {
        push(batch, 0, false);
        if (!splitDungeon) return;
        Hitbox hb = kind.equals("health")
                ? ((AbstractCreature)owner).healthHb : ((AbstractMonster)owner).intentHb;
        if (hb != null) {
            Matrix4 transform = layoutMatrix.idt().translate(-.30f * hb.cX, -.30f * hb.cY, 0)
                    .scale(1.30f, 1.30f, 1);
            batch.setProjectionMatrix(projectedMatrix.set(baseProjection).mul(transform));
        }
    }

    private static void applyLayout(SpriteBatch batch, UiTransform layout) {
        Matrix4 transform = layoutMatrix.idt().translate(layout.dx, layout.dy, 0)
                .scale(layout.scale, layout.scale, 1);
        batch.setProjectionMatrix(projectedMatrix.set(baseProjection).mul(transform));
    }

    public static void beginBackground(SpriteBatch batch) {
        batch.flush();
        backgroundPass = active && splitDungeon && screen == 0;
    }

    public static void endBackground(SpriteBatch batch) {
        try { batch.flush(); }
        finally { backgroundPass = false; }
    }

    public static boolean mirrorBatch() { return backgroundPass; }

    /** Only the GPU mesh submission is duplicated, not the scene's render call. */
    public static void lowerBackgroundViewport() {
        Gdx.gl.glViewport(1024, 0, 1024, 768);
        backgroundBatches++;
    }

    public static void restoreBackgroundViewport() {
        Gdx.gl.glViewport(0, 0, 1024, 768);
    }

    public static void begin(SpriteBatch batch) {
        if (!stack.isEmpty()) throw new IllegalStateException("Unbalanced dual render scope");
        active = true;
        frames++;
        Object roomIdentity = CardCrawlGame.dungeon == null ? null : AbstractDungeon.getCurrRoom();
        if (registeredRoom != roomIdentity || registeredScreen != AbstractDungeon.screen) {
            hitTransforms.clear();
            registeredRoom = roomIdentity;
            registeredScreen = AbstractDungeon.screen;
        }
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
        if (!dungeon && CardCrawlGame.mainMenuScreen != null) {
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
        UiTransform layout = handLayout();
        float startX = layout.x(cx);
        float startY = 816 + 768 - layout.y(cy);
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
                    state.setProperty("handScale", String.valueOf(handLayout().scale));
                    state.setProperty("handRise", String.valueOf(handLayout().dy));
                    state.setProperty("backgroundPolicy", "native-background-mesh-mirror");
                    state.setProperty("backgroundBatches", String.valueOf(backgroundBatches));
                    state.setProperty("controlScale", "1.40");
                    state.setProperty("battleInfoScale", "1.30");
                    state.setProperty("build", "r3-small-screen-20260920-3");
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
