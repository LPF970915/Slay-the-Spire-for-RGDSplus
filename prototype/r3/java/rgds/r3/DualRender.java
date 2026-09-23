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
import com.megacrit.cardcrawl.rooms.AbstractRoom;
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
    private static long touchOrder;
    private static long nextReport;
    private static boolean backgroundPass;
    private static boolean mapPass;
    private static int backgroundBatches;
    private static final Map<Hitbox, UiTransform> hitTransforms = new WeakHashMap<Hitbox, UiTransform>();
    private static final Map<Hitbox, Integer> hitTransformFrames = new WeakHashMap<Hitbox, Integer>();
    private static final Map<Hitbox, TouchHit> touchHits = new WeakHashMap<Hitbox, TouchHit>();
    private static final Matrix4 touchMatrix = new Matrix4();
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

    private static final class TouchHit {
        int frame, panel;
        long order;
        float a, b, c, d, tx, ty;
    }

    /** Menu and slot screens have no map node; the native getter would throw. */
    private static AbstractRoom currentRoom() {
        return CardCrawlGame.dungeon == null || AbstractDungeon.currMapNode == null
                ? null : AbstractDungeon.getCurrRoom();
    }

    public static long touchOrder(Hitbox hb, float x, float y) {
        TouchHit hit = touchHits.get(hb);
        if (hit == null || hit.frame != frames || hit.panel != 1 ||
                registeredScreen != nativeScreenIdentity() ||
                registeredRoom != currentRoom()) return -1;
        float determinant = hit.a * hit.d - hit.b * hit.c;
        if (Math.abs(determinant) < .0001f) return -1;
        float dx = x - hit.tx, dy = 768 - y - hit.ty;
        float nx = (hit.d * dx - hit.b * dy) / determinant;
        float ny = (hit.a * dy - hit.c * dx) / determinant;
        return nx >= hb.x && nx <= hb.x + hb.width && ny >= hb.y &&
                ny <= hb.y + hb.height ? hit.order : -1;
    }

    public static Hitbox touchHitAt(float x, float y) {
        Hitbox result = null;
        long order = -1;
        for (Hitbox hb : touchHits.keySet()) {
            long candidate = touchOrder(hb, x, y);
            if (candidate > order) { order = candidate; result = hb; }
        }
        return result;
    }

    public static void touchPosition(Properties state, String prefix, Hitbox hb) {
        TouchHit hit = touchHits.get(hb);
        if (hit == null || hit.frame != frames || hit.panel != 1) return;
        state.setProperty(prefix + ".x", Float.toString(hit.a * hb.cX + hit.b * hb.cY + hit.tx));
        state.setProperty(prefix + ".y", Float.toString(768 - hit.c * hb.cX - hit.d * hb.cY - hit.ty));
    }

    public static Object touchContext() {
        return CardCrawlGame.mode + "/" + nativeScreenIdentity() + "/" +
                (CardCrawlGame.dungeon == null ? null : currentRoom()) + "/" +
                (CardCrawlGame.cardPopup != null && CardCrawlGame.cardPopup.isOpen) + "/" +
                (CardCrawlGame.relicPopup != null && CardCrawlGame.relicPopup.isOpen) + "/" +
                (CardCrawlGame.mainMenuScreen != null && CardCrawlGame.mainMenuScreen.saveSlotScreen.shown) +
                "/" + UpperInteraction.context() + "/" + TextKeyboard.epoch();
    }

    public static boolean nativeTouchFlow() {
        if (TextKeyboard.active() || CardCrawlGame.cardPopup != null && CardCrawlGame.cardPopup.isOpen ||
                CardCrawlGame.relicPopup != null && CardCrawlGame.relicPopup.isOpen) return false;
        String current = currentPageId();
        return java.util.Arrays.asList("U06", "U13", "U14", "U15", "U16",
                "U17", "U18", "U19", "U20", "U21", "U22", "U23").contains(current);
    }

    public static void cancelTouchHits() {
        for (Hitbox hb : touchHits.keySet()) {
            hb.clickStarted = hb.clicked = hb.hovered = hb.justHovered = false;
        }
    }

    /** Preserve native button click semantics when a lower-panel release is
     * processed after the button's own hitbox update. */
    public static void nativeButtonRelease(Hitbox hb) {
        if (!TouchInput.ownsPointer() || !TouchInput.state.justUp ||
                touchOrder(hb, TouchInput.state.x, TouchInput.state.y) < 0) return;
        hb.clickStarted = false;
        hb.clicked = true;
    }

    public static void recordTouchHit(Hitbox hb, SpriteBatch batch) {
        if (!TouchInput.enabled || !active || CardFlight.visual()) return;
        TouchHit hit = touchHits.get(hb);
        if (hit == null) { hit = new TouchHit(); touchHits.put(hb, hit); }
        float[] m = touchMatrix.set(batch.getProjectionMatrix()).mul(batch.getTransformMatrix()).val;
        float height = mapPass ? 1536 : 768;
        // Interactive mirrored pages (map/chest) render primarily on the lower
        // panel. Upper previews are read-only, even when their mesh is mirrored.
        float viewportY = mapPass && screen == 0 ? -768 : 0;
        hit.a = m[Matrix4.M00] * 512; hit.b = m[Matrix4.M01] * 512;
        hit.c = m[Matrix4.M10] * height / 2; hit.d = m[Matrix4.M11] * height / 2;
        hit.tx = (m[Matrix4.M03] + 1) * 512;
        hit.ty = viewportY + (m[Matrix4.M13] + 1) * height / 2;
        hit.panel = screen; hit.frame = frames;
        hit.order = ++touchOrder;
    }

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
                rememberLayout(card.hb, layout);
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

    public static void logicTick() {
        updates++;
        CardFlight.tick();
        StartupWarmup.tick();
        if (CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY)
            StartupWarmup.stopForGameplay();
    }

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
        if (type.endsWith(".CreditsScreen")) {
            // Credits use one native scroll coordinate over both panels.
            mapPass = true;
            batch.setProjectionMatrix(projectedMatrix.set(baseProjection).scale(1, .5f, 1));
            restoreViewport();
            dimCreditsPanel(batch, 0);
            dimCreditsPanel(batch, 1);
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
        rememberLayout(hb, layout);
    }

    public static void eventOption(SpriteBatch batch, Object owner, int count) {
        push(batch, 1, false);
        Object value = get(owner, "hb");
        if (!(value instanceof Hitbox)) return;
        Hitbox hb = (Hitbox)value;
        Object slotValue = get(owner, "slot");
        int slot = slotValue instanceof Number ? ((Number)slotValue).intValue() : 0;
        count = Math.max(1, count);
        float scale = 1.22f;
        float targetY = 384 + (count - 1) * 52 - slot * 104;
        UiTransform layout = UiTransform.anchored(scale, hb.cX, hb.cY, 512, targetY);
        applyLayout(batch, layout);
        rememberLayout(hb, layout);
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
            rememberLayout(c.hb, layout);
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
        if (screen == 1) ReleaseSignature.draw(batch);
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
                currentRoom() == null) return 1;
        if (currentRoom().event instanceof com.megacrit.cardcrawl.neow.NeowEvent)
            return 0;
        // Generic event text and its speech animation stay on the upper panel.
        // Only LargeDialogOptionButton is routed to the lower touch panel.
        return 0;
    }

    public static void narration(SpriteBatch batch) {
        // Keep Neow's speech bubble at the native single-screen position.
        push(batch, 0, false);
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
        AbstractRoom room = currentRoom();
        return CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                CardCrawlGame.dungeon != null && room != null &&
                room.phase == AbstractRoom.RoomPhase.COMBAT &&
                !room.isBattleOver && !AbstractDungeon.isScreenUp &&
                AbstractDungeon.player != null && !AbstractDungeon.player.isDead;
    }

    public static void pointerBegin(Hitbox hb) {
        if (pointerDepth == pointers.length) throw new IllegalStateException("Nested hitbox overflow");
        int[] saved = pointers[pointerDepth++];
        saved[0] = InputHelper.mX;
        saved[1] = InputHelper.mY;
        saved[2] = 0;
        if (TouchInput.ownsPointer()) {
            saved[2] = 1;
            if (MapTouch.suppressHit(hb)) {
                InputHelper.mX = InputHelper.mY = -10000;
                hb.clickStarted = hb.clicked = false;
                return;
            }
            TouchHit hit = touchHits.get(hb);
            if (hit != null && hit.panel == 1 && hit.frame == frames &&
                    registeredScreen == nativeScreenIdentity() &&
                    registeredRoom == (CardCrawlGame.dungeon == null ? null : currentRoom())) {
                if (TouchInput.state.justDown && touchOrder(hb, TouchInput.state.x, TouchInput.state.y) >= 0)
                {
                    InputHelper.justClickedLeft = true;
                    InputHelper.mX = Math.round(hit.a * hb.cX + hit.b * hb.cY + hit.tx);
                    InputHelper.mY = Math.round(hit.c * hb.cX + hit.d * hb.cY + hit.ty);
                }
                if (TouchInput.state.justUp && hb.clickStarted) {
                    // Validate the final lower-panel position before restoring
                    // native coordinates. Dragging off a button cancels it.
                    boolean inside = touchOrder(hb, TouchInput.state.x, TouchInput.state.y) >= 0;
                    InputHelper.mX = inside ? Math.round(hb.cX) : -10000;
                    InputHelper.mY = inside ? Math.round(hb.cY) : -10000;
                    return;
                }
                float determinant = hit.a * hit.d - hit.b * hit.c;
                if (Math.abs(determinant) > .0001f) {
                    float x = saved[0] - hit.tx, y = saved[1] - hit.ty;
                    InputHelper.mX = Math.round((hit.d * x - hit.b * y) / determinant);
                    InputHelper.mY = Math.round((hit.a * y - hit.c * x) / determinant);
                    return;
                }
            }
            // A lower-screen contact must never activate an upper or unseen hitbox.
            InputHelper.mX = InputHelper.mY = -10000;
            hb.clickStarted = hb.clicked = false;
            return;
        }
        UiTransform layout = hitTransforms.get(hb);
        if (layout != null && registeredScreen == nativeScreenIdentity() &&
                registeredRoom == (CardCrawlGame.dungeon == null ? null : currentRoom()) &&
                Integer.valueOf(frames).equals(hitTransformFrames.get(hb)) &&
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
        rememberLayout(hb, layout);
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

    private static void rememberLayout(Hitbox hb, UiTransform layout) {
        if (hb == null || layout == null) return;
        hitTransforms.put(hb, layout);
        hitTransformFrames.put(hb, frames);
    }

    public static void pushFlight(SpriteBatch batch) {
        push(batch, 1, false);
        mirrorLayout = new UiTransform(1, 0, -816);
        beginBackground(batch);
    }

    public static void pushEffect(SpriteBatch batch, Object effect, String kind) {
        Object overlay = AbstractDungeon.overlayMenu;
        Object owner = get(overlay, kind.equals("energy") ? "energyPanel" :
                kind.equals("draw") ? "combatDeckPanel" :
                kind.equals("discard") ? "discardPilePanel" : "endTurnButton");
        if (owner != null && (kind.equals("energy") || kind.equals("draw") ||
                kind.equals("discard") || kind.equals("end"))) {
            pushControl(batch, owner, kind);
        } else if (kind.equals("hand")) {
            Object card = get(effect, "card");
            if (card != null && !CardFlight.visual() && AbstractDungeon.player != null &&
                    AbstractDungeon.player.hand.group.contains(card))
                push(batch, 1, true);
            else preserve(batch);
        } else preserve(batch);
    }

    public static void preserve(SpriteBatch batch) {
        push(batch, screen, false);
        State saved = stack.peek();
        batch.setProjectionMatrix(saved.projection);
        batch.setTransformMatrix(saved.transform);
        backgroundPass = saved.mirror; mapPass = saved.map; mirrorLayout = saved.preview;
        restoreViewport();
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

    private static String currentPageId() {
        boolean dungeon = CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                CardCrawlGame.dungeon != null;
        String room = dungeon && currentRoom() != null ?
                currentRoom().getClass().getSimpleName() : "";
        return dungeon ? ScreenRoutes.dungeonId(String.valueOf(AbstractDungeon.screen), room) :
                ScreenRoutes.MENU.getOrDefault(String.valueOf(nativeScreenIdentity()), "U33");
    }

    public static void begin(SpriteBatch batch) {
        if (!stack.isEmpty()) throw new IllegalStateException("Unbalanced dual render scope");
        active = true;
        frames++;
        Object roomIdentity = CardCrawlGame.dungeon == null ? null : currentRoom();
        if (registeredRoom != roomIdentity || registeredScreen != nativeScreenIdentity()) {
            hitTransforms.clear();
            hitTransformFrames.clear();
            touchHits.clear();
            registeredRoom = roomIdentity;
            registeredScreen = nativeScreenIdentity();
        }
        baseProjection.set(batch.getProjectionMatrix());
        boolean dungeon = CardCrawlGame.mode == CardCrawlGame.GameMode.GAMEPLAY &&
                CardCrawlGame.dungeon != null && CardCrawlGame.dungeonTransitionScreen == null;
        String room = dungeon && currentRoom() != null
                ? currentRoom().getClass().getSimpleName() : "";
        // Event-triggered fights keep EventRoom as their native room class.
        // Use the room phase, not only the class name, so their hand and
        // combat controls receive the same lower-panel transform.
        splitDungeon = dungeon && combatLayout();
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

    public static void upperBlackOverlay(SpriteBatch batch) {
        if (!pageId.equals("U30")) return;
        Color previous = new Color(batch.getColor());
        push(batch, 0, false);
        batch.setColor(0, 0, 0, .72f);
        batch.draw(ImageMaster.WHITE_SQUARE_IMG, 0, 0, 1024, 768);
        pop(batch);
        batch.setColor(previous);
    }

    public static void dungeonOverlay(SpriteBatch batch) {
        boolean tutorial = AbstractDungeon.screen == AbstractDungeon.CurrentScreen.FTUE;
        push(batch, tutorial ? 1 : 0, false);
        if (!tutorial) beginBackground(batch);
    }

    private static void dimCreditsPanel(SpriteBatch batch, int target) {
        Color previous = new Color(batch.getColor());
        push(batch, target, false);
        batch.setColor(0, 0, 0, .62f);
        batch.draw(ImageMaster.WHITE_SQUARE_IMG, 0, 0, 1024, 768);
        pop(batch);
        batch.setColor(previous);
    }

    public static void targeting(SpriteBatch batch, AbstractPlayer player) {
        boolean self = CombatTouch.selfAiming();
        Object monster = get(player, "hoveredMonster");
        Object card = get(player, "hoveredCard");
        Object hb = self ? player.hb : get(monster, "hb");
        if (card == null || hb == null) return;
        float tx = ((Number)get(hb, "cX")).floatValue();
        float ty = ((Number)get(hb, "cY")).floatValue();
        float cx = ((Number)get(card, "current_x")).floatValue();
        float cy = ((Number)get(card, "current_y")).floatValue();
        UiTransform layout = handLayout();
        float startX = layout.x(cx);
        float startY = 816 + 768 - layout.y(cy);
        float endY = 768 - ty;
        Color color = new Color(batch.getColor());
        if (CombatTouch.card == card) aimCurve.setLocked(startX, startY, tx, endY);
        else aimCurve.set(startX, startY, tx, endY);
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
        Color arrowColor = self ? Color.LIGHT_GRAY : (Color)get(AbstractPlayer.class, "ARROW_COLOR");
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
        upperBlackOverlay(batch);
        PageSummary.render(batch, pageId);
        CardFlight.render(batch);
        DetailControls.render(batch);
        TextKeyboard.render(batch);
        if (CombatTouch.selfAiming()) targeting(batch, AbstractDungeon.player);
        CombatTouch.displayed();
        long now = System.nanoTime();
        if (now >= nextReport) {
            System.out.println("[rgds-r3] frames=" + frames + " updates=" + updates +
                    " logical=" + Settings.WIDTH + "x" + Settings.HEIGHT +
                    " nativeUI=true touchPolicy=" + TouchInput.policy());
            String directory = System.getenv("RGDS_DIAGNOSTICS_DIR");
            if (directory != null) {
                try {
                    Properties state = new Properties();
                    state.setProperty("frames", String.valueOf(frames));
                    state.setProperty("updates", String.valueOf(updates));
                    state.setProperty("nativeUI", "true");
                    state.setProperty("touchPolicy", TouchInput.policy());
                    CombatTouch.diagnostics(state);
                    MapTouch.diagnostics(state);
                    CardFlight.diagnostics(state);
                    CombatEffects.diagnostics(state);
                    UiDiagnostics.collect(state);
                    TextKeyboard.diagnostics(state);
                    state.setProperty("handScale", String.valueOf(handLayout().scale));
                    state.setProperty("handRise", String.valueOf(handLayout().dy));
                    state.setProperty("backgroundPolicy", "native-background-mesh-mirror");
                    state.setProperty("backgroundBatches", String.valueOf(backgroundBatches));
                    state.setProperty("warmup", StartupWarmup.state());
                    state.setProperty("controlScale", "1.40");
                    state.setProperty("battleInfoScale", "1.30");
                    state.setProperty("build", "r4-interface-20260923-12");
                    state.setProperty("mapPolicy", "continuous-1024x1536-native-offset");
                    state.setProperty("menuPolicy", "continuous-bottom-sky-band-tower-1.28");
                    state.setProperty("targetingPolicy", "native-sprites-sticky-enemy-gray-self");
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
