import java.nio.ByteBuffer;
import rgds.TextureInput;

public final class TextureInputTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        for (boolean direct : new boolean[]{false, true}) {
            ByteBuffer rgb = direct ? ByteBuffer.allocateDirect(16) : ByteBuffer.allocate(16);
            rgb.put(new byte[]{99, 1, 2, 3, 4, 5, 6, 88});
            rgb.position(1).limit(7);
            ByteBuffer rgba = TextureInput.rgba(rgb, 2, 1, 6407);
            check(rgba.isDirect() && rgba.position() == 0 && rgba.remaining() == 8, "RGBA size");
            byte[] expected = {1, 2, 3, -1, 4, 5, 6, -1};
            check(TextureInput.cacheSeed(rgba, 0, 8, 123) != 123, "opaque cache invalidated");
            for (byte value : expected) check(rgba.get() == value, "RGB stride and opaque alpha");
            check(rgb.position() == 1 && rgb.limit() == 7, "caller state unchanged");
            check(TextureInput.rgba(rgb, 3, 1, 6407) == null, "short buffer rejected");

            ByteBuffer color = direct ? ByteBuffer.allocateDirect(12) : ByteBuffer.allocate(12);
            color.put(new byte[]{99, 1, 2, 3, 0, 4, 5, 6, 127, 88});
            color.position(1).limit(9);
            ByteBuffer sliced = TextureInput.rgba(color, 2, 1, 6408);
            check(sliced.isDirect() && sliced.position() == 0 && sliced.remaining() == 8,
                    "native base points to first pixel");
            check(sliced.get(0) == 1 && sliced.get(3) == 0 && sliced.get(7) == 127,
                    "RGBA alpha preserved");
            check(TextureInput.cacheSeed(sliced, 0, 8, 123) == 123,
                    "unaffected transparent cache reusable");
            check(color.position() == 1 && color.limit() == 9, "RGBA caller state unchanged");
        }
        ByteBuffer tiny = ByteBuffer.allocateDirect(4);
        check(TextureInput.rgba(tiny, 0, 1, 6407) == null, "zero width");
        check(TextureInput.rgba(tiny, -1, 1, 6407) == null, "negative width");
        check(TextureInput.rgba(tiny, Integer.MAX_VALUE, Integer.MAX_VALUE, 6407) == null,
                "overflow prevented");
        check(TextureInput.rgba(tiny, 1, 1, 123) == null, "unsupported format");
        System.out.println("PASS: RGB/RGBA, direct/heap, offset/limit, alpha, bounds and overflow");
    }
}
