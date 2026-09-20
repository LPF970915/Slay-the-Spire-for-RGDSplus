#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static double milliseconds(void) {
    struct timespec value;
    clock_gettime(CLOCK_MONOTONIC, &value);
    return value.tv_sec * 1000.0 + value.tv_nsec / 1000000.0;
}

static int compare_double(const void *a, const void *b) {
    double left = *(const double *)a, right = *(const double *)b;
    return (left > right) - (left < right);
}

/* Read the real GLES back buffer, not the auxiliary XWayland desktop.
 * Opt-in and bounded: synchronous readback is not part of normal play. */
static void capture(void *sdl, int width, int height) {
    const char *path = getenv("RGDS_CAPTURE_PATH");
    if (!path || !*path || width < 1 || height < 1 ||
            width > 4096 || height > 4096) return;
    void *(*get_proc)(const char *) = dlsym(sdl, "SDL_GL_GetProcAddress");
    if (!get_proc) return;
    void (*get_integer)(unsigned, int *) = get_proc("glGetIntegerv");
    void (*read_pixels)(int, int, int, int, unsigned, unsigned, void *) =
        get_proc("glReadPixels");
    if (!get_integer || !read_pixels) return;
    int framebuffer = -1, pack = 0;
    get_integer(0x8CA6, &framebuffer); /* GL_FRAMEBUFFER_BINDING */
    get_integer(0x0D05, &pack); /* GL_PACK_ALIGNMENT */
    if (framebuffer != 0 || (pack != 1 && pack != 2 && pack != 4 && pack != 8)) {
        fprintf(stderr, "[rgds-sdl] capture skipped framebuffer=%d pack=%d\n",
                framebuffer, pack);
        return;
    }
    size_t row = ((size_t)width * 4 + (size_t)pack - 1) & ~((size_t)pack - 1);
    unsigned char *pixels = calloc((size_t)height, row);
    if (!pixels) return;
    read_pixels(0, 0, width, height, 0x1908, 0x1401, pixels); /* RGBA/UBYTE */
    FILE *out = fopen(path, "wbx");
    if (out) {
        int ok = fprintf(out, "P7\nWIDTH %d\nHEIGHT %d\nDEPTH 4\nMAXVAL 255\n"
                "TUPLTYPE RGB_ALPHA\nENDHDR\n", width, height) > 0;
        for (int y = height - 1; y >= 0; y--)
            if (fwrite(pixels + y * row, 4, (size_t)width, out) != (size_t)width)
                ok = 0;
        if (fclose(out) != 0) ok = 0;
        fprintf(stderr, "[rgds-sdl] capture=%s result=%s size=%dx%d\n",
                path, ok ? "written" : "io-error", width, height);
    } else {
        perror("[rgds-sdl] capture open");
    }
    free(pixels);
}

/* Crusty exports this dispatch shim; keep the change inside this game. */
void _SDL_GL_SwapWindow(void *window) {
    static void (*swap_window)(void *);
    static void *sdl;
    static void (*drawable_size)(void *, int *, int *);
    static unsigned frames;
    static unsigned samples;
    static double next_report, swap_total, swap_max, previous, frame_total, frame_max;
    static double intervals[1024];
    static unsigned interval_count, swap_samples, captures, csv_rows;
    static FILE *csv;
    static int capture_at = 240;
    static int captured;
    static int request_latched;
    static double next_request_check;
    static const char *capture_request;
    if (!swap_window) {
        sdl = dlopen("libSDL2-2.0.so.0", RTLD_NOW | RTLD_LOCAL);
        swap_window = sdl ? dlsym(sdl, "SDL_GL_SwapWindow") : NULL;
        if (!swap_window) {
            fprintf(stderr, "[rgds-sdl] SDL swap unavailable: %s\n", dlerror());
            abort();
        }
        int (*set_interval)(int) = dlsym(sdl, "SDL_GL_SetSwapInterval");
        int (*get_interval)(void) = dlsym(sdl, "SDL_GL_GetSwapInterval");
        const char *setting = getenv("RGDS_SWAP_INTERVAL");
        int interval = setting && strcmp(setting, "1") == 0 ? 1 : 0;
        int result = set_interval ? set_interval(interval) : -1;
        drawable_size = dlsym(sdl, "SDL_GL_GetDrawableSize");
        void (*window_size)(void *, int *, int *) = dlsym(sdl, "SDL_GetWindowSize");
        void (*window_position)(void *, int *, int *) = dlsym(sdl, "SDL_GetWindowPosition");
        int w = 0, h = 0, dw = 0, dh = 0, x = 0, y = 0;
        if (window_size) window_size(window, &w, &h);
        if (drawable_size) drawable_size(window, &dw, &dh);
        if (window_position) window_position(window, &x, &y);
        fprintf(stderr, "[rgds-sdl] swap interval=%d result=%d actual=%d "
                "window=%dx%d drawable=%dx%d position=%d,%d\n", interval, result,
                get_interval ? get_interval() : -99, w, h, dw, dh, x, y);
        const char *frame = getenv("RGDS_CAPTURE_FRAME");
        if (frame && atoi(frame) >= 0) capture_at = atoi(frame);
        capture_request = getenv("RGDS_CAPTURE_REQUEST");
        const char *csv_path = getenv("RGDS_FRAME_CSV");
        if (csv_path && *csv_path) {
            csv = fopen(csv_path, "wx");
            if (csv) fprintf(csv, "monotonic_ms,frame_ms,swap_ms,capture\n");
            else perror("[rgds-sdl] frame CSV");
        }
        next_report = milliseconds() + 5000;
    }
    frames++;
    int requested = 0, capture_frame = 0;
    double check_time = milliseconds();
    if (capture_request && check_time >= next_request_check) {
        int present = access(capture_request, F_OK) == 0;
        requested = present && !request_latched;
        request_latched = present;
        next_request_check = check_time + 250;
    }
    if (drawable_size && captures < 64 &&
            ((!captured && frames == (unsigned)capture_at) || requested)) {
        if (frames == (unsigned)capture_at) captured = 1;
        captures++;
        capture_frame = 1;
        int width = 0, height = 0;
        drawable_size(window, &width, &height);
        capture(sdl, width, height);
    }
    double begin = milliseconds();
    double frame_elapsed = previous ? begin - previous : 0;
    if (previous) {
        frame_total += frame_elapsed;
        if (frame_elapsed > frame_max) frame_max = frame_elapsed;
        if (interval_count < 1024) intervals[interval_count++] = frame_elapsed;
        samples++;
    }
    previous = begin;
    swap_window(window);
    double end = milliseconds(), elapsed = end - begin;
    swap_total += elapsed;
    swap_samples++;
    if (elapsed > swap_max) swap_max = elapsed;
    if (csv && csv_rows++ < 250000)
        fprintf(csv, "%.3f,%.3f,%.3f,%d\n", begin, frame_elapsed, elapsed, capture_frame);
    else if (csv) {
        fclose(csv);
        csv = NULL;
    }
    if (end >= next_report) {
        qsort(intervals, interval_count, sizeof(double), compare_double);
        double p95 = interval_count ? intervals[(interval_count * 95 + 99) / 100 - 1] : 0;
        double p99 = interval_count ? intervals[(interval_count * 99 + 99) / 100 - 1] : 0;
        fprintf(stderr, "[rgds-sdl] frames=%u frame_mean_ms=%.2f frame_max_ms=%.2f "
                "p95_ms=%.2f p99_ms=%.2f swap_mean_ms=%.2f swap_max_ms=%.2f\n", samples,
                samples ? frame_total / samples : 0, frame_max,
                p95, p99, swap_samples ? swap_total / swap_samples : 0, swap_max);
        samples = interval_count = swap_samples = 0;
        frame_total = frame_max = swap_total = swap_max = 0;
        next_report = end + 5000;
        if (csv) fflush(csv);
    }
}
