#define _SDL_GL_SwapWindow r3_base_swap
#include "../../platform/rgds_sdl.c"
#undef _SDL_GL_SwapWindow
#include <sys/syscall.h>

static void *dual_window;
static long video_thread;

void _SDL_GL_SwapWindow(void *window) {
    static double next_focus;
    static unsigned previous_flags = ~0u;
    const char *directory = getenv("RGDS_DIAGNOSTICS_DIR");
    if (directory && milliseconds() >= next_focus) {
        void *sdl = dlopen("libSDL2-2.0.so.0", RTLD_NOW | RTLD_LOCAL);
        unsigned (*flags)(void *) = dlsym(sdl, "SDL_GetWindowFlags");
        void (*pump)(void) = dlsym(sdl, "SDL_PumpEvents");
        /* LWJGL owns the game loop; refresh SDL state on its video thread. */
        if (pump && syscall(SYS_gettid) == video_thread) pump();
        char temporary[1024], path[1024];
        unsigned value = flags ? flags(window) : 0;
        if (value != previous_flags) {
            fprintf(stderr, "[rgds-r3] window_flags=0x%x video_thread=%ld swap_thread=%ld\n",
                    value, video_thread, syscall(SYS_gettid));
            previous_flags = value;
        }
        snprintf(temporary, sizeof(temporary), "%s/window-focus.tmp", directory);
        snprintf(path, sizeof(path), "%s/window-focus.txt", directory);
        FILE *file = fopen(temporary, "w");
        if (file) {
            fprintf(file, "%d %.6f\n",
                    (value & 0x200u) != 0 && (value & 0x40u) == 0,
                    milliseconds() / 1000.0);
            fclose(file);
            rename(temporary, path);
        }
        next_focus = milliseconds() + 250;
    }
    r3_base_swap(window);
}

/* Keep LWJGL's logical 4:3 surface while exposing both physical outputs. */
void *_SDL_CreateWindow(const char *title, int x, int y, int w, int h, unsigned flags) {
    void *sdl = dlopen("libSDL2-2.0.so.0", RTLD_NOW | RTLD_LOCAL);
    void *(*create)(const char *, int, int, int, int, unsigned) =
        dlsym(sdl, "SDL_CreateWindow");
    if (!create) abort();
    if (w == 1024 && h == 768) {
        flags &= ~(1u | 0x1000u | 0x20u);
        flags |= 0x10u;
        video_thread = syscall(SYS_gettid);
        dual_window = create(title, 0, 0, 2048, 768, flags);
        fprintf(stderr, "[rgds-r3] physical=2048x768 logical=1024x768 window=%p\n",
                dual_window);
        return dual_window;
    }
    return create(title, x, y, w, h, flags);
}

void _SDL_GetWindowSize(void *window, int *width, int *height) {
    if (window == dual_window && window) {
        if (width) *width = 1024;
        if (height) *height = 768;
        return;
    }
    void *sdl = dlopen("libSDL2-2.0.so.0", RTLD_NOW | RTLD_LOCAL);
    void (*size)(void *, int *, int *) = dlsym(sdl, "SDL_GetWindowSize");
    if (!size) abort();
    size(window, width, height);
}
