package rgds.r3;

import java.lang.management.ManagementFactory;

/** Bounded counters only; no per-frame allocation or file output. */
public final class PerfProbe {
    private static final boolean ENABLED = "1".equals(System.getenv("RGDS_R3_PROFILE"));
    private static long renderStart, updateStart, renderTotal, updateTotal, renderMax, updateMax;
    private static long nextReport;
    private static int frames;

    public static void renderBegin() {
        if (ENABLED) renderStart = System.nanoTime();
    }

    public static void updateBegin() {
        if (ENABLED) updateStart = System.nanoTime();
    }

    public static void updateEnd() {
        if (!ENABLED) return;
        long elapsed = System.nanoTime() - updateStart;
        updateTotal += elapsed;
        updateMax = Math.max(updateMax, elapsed);
    }

    public static void renderEnd() {
        if (!ENABLED) return;
        long now = System.nanoTime(), elapsed = now - renderStart;
        renderTotal += elapsed;
        renderMax = Math.max(renderMax, elapsed);
        frames++;
        if (now < nextReport) return;
        Runtime runtime = Runtime.getRuntime();
        System.out.println("[r3-perf] mono_ms=" + now / 1000000 +
                " uptime_ms=" + ManagementFactory.getRuntimeMXBean().getUptime() +
                " frames=" + frames +
                " render_mean_us=" + renderTotal / frames / 1000 +
                " render_max_us=" + renderMax / 1000 +
                " update_mean_us=" + updateTotal / frames / 1000 +
                " update_max_us=" + updateMax / 1000 +
                " heap_used_kb=" + (runtime.totalMemory() - runtime.freeMemory()) / 1024 +
                " heap_committed_kb=" + runtime.totalMemory() / 1024);
        frames = 0;
        renderTotal = updateTotal = renderMax = updateMax = 0;
        nextReport = now + 5000000000L;
    }
}
