package rgds.r3;

import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import java.net.InetSocketAddress;
import java.nio.ByteBuffer;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.nio.file.StandardCopyOption;

/** Loopback input transport polled only on the game's existing update thread. */
public final class TouchInput {
    public static final boolean enabled = "1".equals(System.getenv("RGDS_R4_TOUCH_LIVE"));
    public static final TouchState state = new TouchState();
    private static final int[] PAD_KEYS = {19, 20, 21, 22, 62, 131, 52, 66, 45, 33, 41, 61, 29, 46};
    private static ServerSocketChannel server;
    private static SocketChannel client;
    private static final ByteBuffer buffer = ByteBuffer.allocate(32 * 128);
    private static Object context;
    private static long accepted, nextReport;
    private static boolean failed;
    private static boolean touchCursor;
    private static int heldPadKeys;
    public static long padVersion;

    public static String policy() { return enabled ? "native-lower-pointer" : "capture-only"; }
    public static boolean ownsPointer() { return enabled && state.owned; }
    public static boolean hideCursor() { return enabled && touchCursor; }

    private static void disconnect() throws java.io.IOException {
        if (client != null) client.close();
        client = null;
        buffer.clear();
        state.cancel();
    }

    public static boolean poll() {
        if (!enabled) return false;
        boolean hadTouch = state.owned;
        double now = System.nanoTime() / 1e9;
        try {
            if (server == null && !failed) {
                server = ServerSocketChannel.open();
                server.bind(new InetSocketAddress("127.0.0.1", 0));
                server.configureBlocking(false);
                Path directory = Path.of(System.getenv("RGDS_DIAGNOSTICS_DIR"));
                Path temporary = directory.resolve("touch-port.tmp");
                Files.write(temporary, Integer.toString(
                        ((InetSocketAddress)server.getLocalAddress()).getPort()).getBytes(StandardCharsets.US_ASCII));
                Files.move(temporary, directory.resolve("touch-port.txt"), StandardCopyOption.REPLACE_EXISTING);
                System.out.println("[r4-touch] loopback ready");
            }
            if (server != null && client == null) {
                client = server.accept();
                if (client != null) { client.configureBlocking(false); state.cancel(); }
            }
            if (client != null) {
                int count = client.read(buffer);
                if (count < 0) disconnect();
                else {
                    buffer.flip();
                    while (buffer.remaining() >= 32) {
                        if (buffer.getInt() != 0x53545331) {
                            disconnect();
                            break;
                        }
                        int kind = buffer.getInt();
                        double time = buffer.getDouble();
                        float x = buffer.getFloat(), y = buffer.getFloat();
                        long gesture = buffer.getLong();
                        state.accept(kind, time, x, y, gesture, now);
                        if (kind != TouchState.HEARTBEAT) accepted++;
                    }
                    if (client != null) buffer.compact();
                }
            }
        } catch (Exception error) {
            state.cancel();
            if (!failed) { System.err.println("[r4-touch] input unavailable: " + error); failed = true; }
            try { disconnect(); } catch (java.io.IOException ignored) { }
        }
        Object current = DualRender.touchContext();
        if (context != null && !context.equals(current)) state.cancel();
        context = current;
        int keys = 0;
        for (int i = 0; i < PAD_KEYS.length; i++)
            if (rgds.InputEdges.pressed(PAD_KEYS[i])) keys |= 1 << i;
        if ((keys & ~heldPadKeys) != 0) padVersion++;
        heldPadKeys = keys;
        boolean pad = keys != 0;
        if (pad && (state.owned || state.hasPending())) state.cancel();
        if (pad) touchCursor = false;
        boolean cancel = state.advance(now);
        if (cancel) {
            MapTouch.cancel();
            CombatTouch.cancel();
            TextKeyboard.cancelContact();
            DualRender.cancelTouchHits();
            if (hadTouch && AbstractDungeon.player != null &&
                    (AbstractDungeon.player.isDraggingCard || AbstractDungeon.player.inSingleTargetMode))
                AbstractDungeon.player.releaseCard();
        }
        if (state.justDown) touchCursor = true;
        else touchCursor = state.owned || touchCursor && !pad;
        if (state.justDown && UpperInteraction.cancelForTouch()) {
            state.cancel();
            CombatTouch.cancel();
            DualRender.cancelTouchHits();
            cancel = true;
        }
        if (state.justDown && DualRender.nativeTouchFlow()) {
            System.out.println("[r4-touch] down-hit=" +
                    (DualRender.touchHitAt(state.x, state.y) != null) +
                    " point=" + state.x + "," + state.y);
        }
        // Native reward, selection, shop and campfire pages use a guarded
        // touch flow: select first, then confirm. Combat drag aiming and the
        // custom map gesture retain the mouse-style path already used by R4.
        boolean nativeTouch = ownsPointer() && DualRender.nativeTouchFlow();
        Settings.TOUCHSCREEN_ENABLED = nativeTouch;
        Settings.isTouchScreen = nativeTouch;
        if (System.nanoTime() >= nextReport) {
            System.out.println("[r4-touch] received=" + accepted + " owned=" + state.owned +
                    " down=" + state.down + " point=" + state.x + "," + state.y);
            nextReport = System.nanoTime() + 5_000_000_000L;
        }
        return cancel;
    }

}
