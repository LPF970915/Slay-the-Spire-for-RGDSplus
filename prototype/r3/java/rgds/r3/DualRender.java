package rgds.r3;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.badlogic.gdx.graphics.g2d.TextureRegion;
import com.badlogic.gdx.math.Matrix4;
import com.badlogic.gdx.math.Interpolation;
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
    private static final Map<Class<?>, Integer> eventRoutes = new HashMap<Class<?>, Integer>();
    private static int screen;
    private static int frames, updates;
    private static long nextReport;
    private static boolean backgroundPass;
    private static boolean mapPass;
    private static int backgroundBatches;
    private static final Map<Hitbox, UiTransform> hitTransforms = new WeakHashMap<Hitbox, UiTransform>();
    private static final int[][] pointers = new int[32][3];
    private static int pointerDepth;
    private static boolean active;
    private static boolean splitDungeon;
    private static boolean routedDungeon;
    private static String pageId = "U01";
    private static String pageClass = "";
    private static final java.util.Set<String> seenPages = new java.util.LinkedHashSet<String>();
    private static final Matrix4 baseProjection = new Matrix4();
    private static final Matrix4 layoutMatrix = new Matrix4();
    private static final Matrix4 projectedMatrix = new Matrix4();
    private static final Matrix4 mirrorCombined = new Matrix4();
    private static UiTransform mirrorLayout;
    private static final TextureRegion lowerSky = new TextureRegion();
    private static Object registeredRoom;
    private static Object registeredScreen;
    private static final AimCurve aimCurve = new AimCurve();
    private static final com.badlogic.gdx.math.Vector2 curvePoint = new com.badlogic.gdx.math.Vector2();
    private static final float[] curveX = new float[96], curveY = new float[96];
    private static final float[] curveAngle = new float[96], curveScale = new float[96];
    private static Object aimCard;
    private static int lastAimFrame = -1;
    private static float aimTimer;

    private static final class State {
        int screen;
        boolean mirror;
        boolean map;
        UiTransform preview;
        final Matrix4 transform = new Matrix4();
        final Matrix4 projection = new Matrix4();
        void save(SpriteBatch batch) {
            screen = DualRender.screen;
            mirror = backgroundPass;
            map = mapPass;
            preview = mirrorLayout;
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

    private static void restoreViewport() {
        Gdx.gl.glViewport(screen * 1024, mapPass && screen == 0 ? -768 : 0,
                1024, mapPass ? 1536 : 768);
    }

    public static void mapEffect(SpriteBatch batch) {
        boolean map = CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                AbstractDungeon.screen == AbstractDungeon.CurrentScreen.MAP;
        push(batch, map ? 1 : screen, false);
        if (map) {
            mapPass = true;
            batch.setProjectionMatrix(projectedMatrix.set(baseProjection).scale(1, .5f, 1));
            restoreViewport();
            beginBackground(batch);
        }
    }

    public static void push(SpriteBatch batch, int target, boolean hand) {
        if (!active) return;
        State saved = freeStates.pollFirst();
        if (saved == null) saved = new State();
        saved.save(batch);
        stack.push(saved);
        viewport(batch, target);
        backgroundPass = false;
        mirrorLayout = null;
        mapPass = false;
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
        backgroundPass = state.mirror;
        mapPass = state.map;
        mirrorLayout = state.preview;
        restoreViewport();
        freeStates.addFirst(state);
    }

    public static void logicTick() { updates++; }

    public static void page(SpriteBatch batch, int target, boolean mirror, String id, String type) {
        push(batch, target, false);
        // A render visit can be an invisible popup or the always-rendered top bar.
        // The active page identity comes from native screen state, not call order.
        if (seenPages.add(type)) System.out.println("[r4-route] " + id + " " + type);
        if (type.endsWith(".DungeonMapScreen")) {
            mapPass = true;
            batch.setProjectionMatrix(projectedMatrix.set(baseProjection).scale(1, .5f, 1));
            restoreViewport();
        }
        if (mirror) beginBackground(batch);
    }

    public static void titleLayer(SpriteBatch batch, Object owner, Object region, float y) {
        boolean bottom = region == get(owner, "mg3Bot") || region == get(owner, "botGlow");
        boolean sky = region == get(owner, "sky");
        push(batch, bottom ? 1 : 0, false);
        if (sky) {
            // Continue the lowest sky band instead of repeating the turquoise top.
            push(batch, 1, false);
            drawLowerSky(batch, (TextureRegion)region);
            pop(batch);
        } else if (bottom) {
            float scale = 1.28f;
            Matrix4 transform = layoutMatrix.idt().translate(160 * (1 - scale),
                    768 - scale * (y + 1140 * Settings.scale), 0).scale(scale, scale, 1);
            batch.setProjectionMatrix(projectedMatrix.set(baseProjection).mul(transform));
        } else {
            float scaleY = 768 / (1140 * Settings.scale);
            Matrix4 transform = layoutMatrix.idt().translate(0, -y * scaleY, 0).scale(1, scaleY, 1);
            batch.setProjectionMatrix(projectedMatrix.set(baseProjection).mul(transform));
        }
    }

    public static boolean midCloud(Object owner, Object cloud) {
        return ((java.util.List<?>)get(owner, "midClouds")).contains(cloud);
    }

    private static void drawLowerSky(SpriteBatch batch, TextureRegion sky) {
        lowerSky.setRegion(sky);
        lowerSky.setV(sky.getV2() - (sky.getV2() - sky.getV()) * .025f);
        batch.draw(lowerSky, 0, 0, 1024, 768);
    }

    public static void smallControl(SpriteBatch batch, Object owner, boolean mainMenu) {
        push(batch, 1, false);
        Object value = get(owner, "hb");
        if (!(value instanceof Hitbox)) return;
        Hitbox hb = (Hitbox)value;
        UiTransform layout;
        if (mainMenu) {
            layout = new UiTransform(1.65f, 24, 44);
        } else if (pageId.equals("U14") && owner.getClass().getSimpleName().equals("CardSelectConfirmButton")) {
            layout = UiTransform.anchored(1.22f, hb.cX, hb.cY, 512, 70);
        } else {
            float scale = 1.22f;
            float marginX = Math.min(496, hb.width * scale / 2 + 16);
            float marginY = Math.min(368, hb.height * scale / 2 + 16);
            float x = Math.max(marginX, Math.min(1024 - marginX, hb.cX));
            float y = Math.max(marginY, Math.min(768 - marginY, hb.cY));
            layout = UiTransform.anchored(scale, hb.cX, hb.cY, x, y);
        }
        applyLayout(batch, layout);
        hitTransforms.put(hb, layout);
    }

    public static void eventOption(SpriteBatch batch, Object owner) {
        push(batch, 1, false);
        Object value = get(owner, "hb");
        if (!(value instanceof Hitbox)) return;
        Hitbox hb = (Hitbox)value;
        Object slotValue = get(owner, "slot");
        int slot = slotValue instanceof Number ? ((Number)slotValue).intValue() : 0;
        float scale = 1.22f;
        float targetY = 480 - slot * 105;
        UiTransform layout = UiTransform.anchored(scale, hb.cX, hb.cY, 512, targetY);
        applyLayout(batch, layout);
        hitTransforms.put(hb, layout);
    }

    public static void preview(SpriteBatch batch, Object item, Object owner) {
        if (!ScreenRoutes.previewPage(pageId)) {
            push(batch, screen, false);
            State saved = stack.peek();
            batch.setProjectionMatrix(saved.projection);
            batch.setTransformMatrix(saved.transform);
            backgroundPass = saved.mirror;
            mapPass = saved.map;
            mirrorLayout = saved.preview;
            restoreViewport();
            return;
        }
        push(batch, 1, false);
        Object hb = get(item, "hb");
        if (pageId.equals("U14") && item instanceof com.megacrit.cardcrawl.cards.AbstractCard &&
                AbstractDungeon.player.hand.group.contains(item)) {
            com.megacrit.cardcrawl.cards.AbstractCard c = (com.megacrit.cardcrawl.cards.AbstractCard)item;
            boolean hovered = c == get(AbstractDungeon.player, "hoveredCard") ||
                    c == AbstractDungeon.handCardSelectScreen.hoveredCard;
            float scale = Math.min(1.20f, handLayout().scale);
            UiTransform layout = UiTransform.anchored(scale, 512, c.current_y, 512, hovered ? 235 : 195);
            applyLayout(batch, layout);
            hitTransforms.put(c.hb, layout);
        }
        if ((hb instanceof Hitbox && ((Hitbox)hb).hovered) ||
                item == get(owner, "hoveredCard") || item == get(owner, "upgradePreviewCard") ||
                pageId.equals("U14") && item == get(AbstractDungeon.player, "hoveredCard"))
        {
            float x, y, scale;
            if (item instanceof com.megacrit.cardcrawl.cards.AbstractCard) {
                com.megacrit.cardcrawl.cards.AbstractCard c = (com.megacrit.cardcrawl.cards.AbstractCard)item;
                x = c.current_x; y = c.current_y;
                scale = Math.min(3.8f, 1.9f / Math.max(.1f, c.drawScale));
            } else {
                Hitbox hit = (Hitbox)hb;
                x = hit.cX; y = hit.cY; scale = 1.8f;
            }
            mirrorLayout = UiTransform.anchored(scale, x, y, 512, 384);
            beginBackground(batch);
        }
    }

    public static void endPage(SpriteBatch batch, boolean mirror) {
        if (mirror) endBackground(batch);
        pop(batch);
    }

    public static int roomTarget(Object room) {
        return ScreenRoutes.knownRoom(room.getClass().getSimpleName()) ? 0 : 1;
    }

    public static int eventTarget(Object event) {
        if (event instanceof com.megacrit.cardcrawl.neow.NeowEvent) return 0;
        if (!(event instanceof com.megacrit.cardcrawl.events.AbstractImageEvent)) return 1;
        Class<?> type = event.getClass();
        Integer cached = eventRoutes.get(type);
        if (cached != null) return cached;
        int target = 0;
        for (Class<?> cls = type; cls != com.megacrit.cardcrawl.events.AbstractImageEvent.class;
                cls = cls.getSuperclass()) {
            for (String name : new String[]{"render", "renderAboveTopPanel"}) {
                try {
                    cls.getDeclaredMethod(name, SpriteBatch.class);
                    target = 1;
                } catch (NoSuchMethodException expected) { }
            }
        }
        eventRoutes.put(type, target);
        return target;
    }

    public static int dialogTarget() {
        if (CardCrawlGame.mode != CardCrawlGame.GameMode.GAMEPLAY ||
                AbstractDungeon.getCurrRoom() == null) return 1;
        if (AbstractDungeon.getCurrRoom().event instanceof com.megacrit.cardcrawl.neow.NeowEvent)
            return 1;
        // Generic event text and its speech animation stay on the upper panel.
        // Only LargeDialogOptionButton is routed to the lower touch panel.
        return 0;
    }

    public static void narration(SpriteBatch batch) {
        boolean neow = CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                AbstractDungeon.getCurrRoom() != null &&
                AbstractDungeon.getCurrRoom().event instanceof com.megacrit.cardcrawl.neow.NeowEvent;
        push(batch, neow ? 1 : 0, false);
        if (neow) applyLayout(batch, new UiTransform(1.25f, -128, 60));
    }

    public static int tipTarget() {
        if (CardCrawlGame.cardPopup != null && CardCrawlGame.cardPopup.isOpen) return 0;
        if (CardCrawlGame.relicPopup != null && CardCrawlGame.relicPopup.isOpen) return 0;
        if (ScreenRoutes.previewPage(pageId)) return 0;
        return CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                !AbstractDungeon.isScreenUp ? 0 : 1;
    }

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
        if (layout != null && registeredScreen == nativeScreenIdentity() &&
                registeredRoom == (CardCrawlGame.dungeon == null ? null : AbstractDungeon.getCurrRoom()) &&
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
        backgroundPass = active;
    }

    public static void endBackground(SpriteBatch batch) {
        try { batch.flush(); }
        finally { backgroundPass = false; }
    }

    public static boolean mirrorBatch() { return backgroundPass; }

    /** Only the GPU mesh submission is duplicated, not the scene's render call. */
    public static void lowerBackgroundViewport(SpriteBatch batch) {
        Gdx.gl.glViewport((1 - screen) * 1024, mapPass && screen == 1 ? -768 : 0,
                1024, mapPass ? 1536 : 768);
        if (mirrorLayout != null) {
            mirrorCombined.set(baseProjection).translate(mirrorLayout.dx, mirrorLayout.dy, 0)
                    .scale(mirrorLayout.scale, mirrorLayout.scale, 1).mul(batch.getTransformMatrix());
            batch.getShader().setUniformMatrix("u_projTrans", mirrorCombined);
        }
        backgroundBatches++;
    }

    public static void restoreBackgroundViewport(SpriteBatch batch) {
        if (mirrorLayout != null)
            batch.getShader().setUniformMatrix("u_projTrans",
                    mirrorCombined.set(batch.getProjectionMatrix()).mul(batch.getTransformMatrix()));
        restoreViewport();
    }

    private static Object nativeScreenIdentity() {
        return CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY ? AbstractDungeon.screen :
                CardCrawlGame.mainMenuScreen == null ? null : CardCrawlGame.mainMenuScreen.screen;
    }

    public static void begin(SpriteBatch batch) {
        if (!stack.isEmpty()) throw new IllegalStateException("Unbalanced dual render scope");
        active = true;
        frames++;
        Object roomIdentity = CardCrawlGame.dungeon == null ? null : AbstractDungeon.getCurrRoom();
        if (registeredRoom != roomIdentity || registeredScreen != nativeScreenIdentity()) {
            hitTransforms.clear();
            registeredRoom = roomIdentity;
            registeredScreen = nativeScreenIdentity();
        }
        baseProjection.set(batch.getProjectionMatrix());
        boolean dungeon = CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                CardCrawlGame.dungeon != null && CardCrawlGame.dungeonTransitionScreen == null;
        String room = dungeon && AbstractDungeon.getCurrRoom() != null
                ? AbstractDungeon.getCurrRoom().getClass().getSimpleName() : "";
        splitDungeon = dungeon && room.startsWith("MonsterRoom");
        routedDungeon = dungeon && ScreenRoutes.knownRoom(room);
        String nativeScreen = dungeon ? String.valueOf(AbstractDungeon.screen) :
                CardCrawlGame.mainMenuScreen == null ? "NONE" :
                String.valueOf(CardCrawlGame.mainMenuScreen.screen);
        pageId = dungeon ? ScreenRoutes.dungeonId(nativeScreen, room) :
                ScreenRoutes.MENU.getOrDefault(nativeScreen, "U33");
        if (dungeon && nativeScreen.equals("CARD_REWARD") &&
                Boolean.TRUE.equals(get(AbstractDungeon.cardRewardScreen, "chooseOne"))) pageId = "U16";
        if (splitDungeon && !AbstractDungeon.isScreenUp &&
                Boolean.TRUE.equals(get(AbstractDungeon.player, "inSingleTargetMode"))) pageId = "U09";
        if (CardCrawlGame.cardPopup != null && CardCrawlGame.cardPopup.isOpen ||
                CardCrawlGame.relicPopup != null && CardCrawlGame.relicPopup.isOpen) pageId = "U25";
        if (CardCrawlGame.dungeonTransitionScreen != null) pageId = "U01";
        if (CardCrawlGame.mode == CardCrawlGame.GameMode.SPLASH) pageId = "U01";
        if (!dungeon && CardCrawlGame.mainMenuScreen != null &&
                CardCrawlGame.mainMenuScreen.saveSlotScreen.shown) pageId = "U03";
        if (dungeon && !AbstractDungeon.topPanel.potionUi.isHidden) pageId = "U12";
        pageClass = CardCrawlGame.mode + "/" + nativeScreen + "/" + room;
        viewport(batch, routedDungeon && ScreenRoutes.DUNGEON.containsKey(nativeScreen) ? 0 : 1);
        Color color = new Color(batch.getColor());
        push(batch, 1, false);
        batch.setColor(Color.WHITE);
        if (!dungeon && CardCrawlGame.mode == CardCrawlGame.GameMode.CHAR_SELECT &&
                CardCrawlGame.dungeonTransitionScreen == null &&
                CardCrawlGame.mainMenuScreen != null) {
            Object bg = get(CardCrawlGame.mainMenuScreen, "bg");
            Object sky = get(bg, "sky");
            if (sky instanceof TextureRegion)
                drawLowerSky(batch, (TextureRegion)sky);
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
        aimCurve.set(startX, startY, tx, endY);
        float length = 0, previousX = startX, previousY = startY;
        for (int i = 1; i <= 160; i++) {
            aimCurve.point(curvePoint, i / 160f);
            length += (float)Math.hypot(curvePoint.x - previousX, curvePoint.y - previousY);
            previousX = curvePoint.x;
            previousY = curvePoint.y;
        }
        int segments = AimCurve.segments(length, Settings.scale);
        for (int i = 0; i < segments; i++) {
            float t = i / (float)segments;
            aimCurve.point(curvePoint, t);
            curveX[i] = curvePoint.x;
            curveY[i] = curvePoint.y;
            curveAngle[i] = aimCurve.angle(t);
            curveScale[i] = AimCurve.bodyScale(t, Settings.scale);
        }
        // Advance visual animation once, before submitting to both panels.
        if (lastAimFrame != frames) {
            if (lastAimFrame != frames - 1 || aimCard != card) aimTimer = 0;
            aimTimer = Math.min(1, aimTimer + Gdx.graphics.getDeltaTime());
            aimCard = card;
            lastAimFrame = frames;
        }
        float tipScale = Interpolation.elasticOut.apply(Settings.scale, Settings.scale * 1.2f, aimTimer);
        Color arrowColor = (Color)get(AbstractPlayer.class, "ARROW_COLOR");
        for (int target = 0; target < 2; target++) {
            push(batch, target, false);
            batch.setColor(arrowColor);
            // Submit complete native sprites on both panels. GPU clipping retains
            // edge fragments even when the sprite's center lies in the bezel.
            for (int i = 0; i < segments; i++) {
                batch.draw(ImageMaster.TARGET_UI_CIRCLE,
                        curveX[i] - 64, AimCurve.panelY(curveY[i], target) - 64,
                        64, 64, 128, 128, curveScale[i], curveScale[i], curveAngle[i],
                        0, 0, 128, 128, false, false);
            }
            batch.draw(ImageMaster.TARGET_UI_ARROW, tx - 128, AimCurve.panelY(endY, target) - 128,
                    128, 128, 256, 256, tipScale, tipScale, aimCurve.arrowAngle(),
                    0, 0, 256, 256, false, false);
            pop(batch);
        }
        batch.setColor(color);
    }

    public static void finish(SpriteBatch batch) {
        if (!stack.isEmpty()) throw new IllegalStateException("Unbalanced dual scopes at frame end");
        PageSummary.render(batch, pageId);
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
                    state.setProperty("build", "r4-layout-20260920-7");
                    state.setProperty("mapPolicy", "continuous-1024x1536-native-offset");
                    state.setProperty("menuPolicy", "continuous-bottom-sky-band-tower-1.28");
                    state.setProperty("targetingPolicy", "native-red-sprites-quadratic-gpu-clipped");
                    state.setProperty("mode", String.valueOf(CardCrawlGame.mode));
                    state.setProperty("screen", String.valueOf(AbstractDungeon.screen));
                    state.setProperty("layout", splitDungeon ? "battle-split" : routedDungeon ? "room-split" : "menu-or-lower-fallback");
                    state.setProperty("pageId", pageId);
                    state.setProperty("reviewScene", ReviewProbe.scene());
                    state.setProperty("pageClass", pageClass);
                    state.setProperty("seenPages", String.join(",", seenPages));
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
