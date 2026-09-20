package rgds;

import java.nio.ByteBuffer;

/** The upstream native ASTC entry point always consumes tightly packed RGBA. */
public final class TextureInput {
    private TextureInput() {}

    public static long cacheSeed(ByteBuffer source, int offset, int length, long seed) {
        // Legacy transparent RGBA entries were not down-converted. Opaque entries
        // may contain the native RGB-stride bug and must never be reused.
        if (offset < 0 || length < 0 || (long) offset + length > source.limit()
                || length % 4 != 0) throw new IllegalArgumentException("Invalid RGBA hash range");
        for (int i = offset + 3; i < offset + length; i += 4)
            if (source.get(i) != (byte) 255) return seed;
        return seed ^ 0x5247445352474233L;
    }

    public static ByteBuffer rgba(ByteBuffer source, int width, int height, int format) {
        if (width <= 0 || height <= 0 || (format != 6407 && format != 6408)) return null;
        long pixels = (long) width * height;
        int channels = format == 6407 ? 3 : 4;
        if (pixels > Integer.MAX_VALUE / 4 || pixels * channels > source.remaining())
            return null;
        // JNI GetDirectBufferAddress ignores position; slice starts at the actual data.
        ByteBuffer input = source.slice();
        input.limit((int) pixels * channels);
        if (channels == 4 && input.isDirect()) return input;
        ByteBuffer output = ByteBuffer.allocateDirect((int) pixels * 4);
        if (channels == 4) {
            output.put(input);
        } else {
            while (input.hasRemaining()) {
                output.put(input.get()).put(input.get()).put(input.get()).put((byte) 255);
            }
        }
        output.flip();
        return output;
    }
}
