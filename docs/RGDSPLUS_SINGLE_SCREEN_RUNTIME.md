# RGDSplus runtime notes

The device baseline used by this project is:

- RK3568, aarch64, four Cortex-A55 cores
- Buildroot 2024.02, glibc 2.41
- Linux 6.1.141, Weston 14.0.2
- two 1024x768 DSI outputs
- approximately 976 MB RAM and no swap

For the P0 port the application remains a normal 1024x768 window. The
launcher mounts the PortMaster Java 17 and Weston wrapper runtimes, then uses
an auxiliary headless XWayland server for LWJGL's X11 calls. Crusty's SDL
window uses `CRUSTY_WLMODE=1`, `SDL_VIDEODRIVER=wayland`, and the absolute
firmware Wayland socket, so presentation stays with the system compositor.
It does not create a 2048x768 drawable. Physical output placement and gameplay
stability still require device testing.

The private installation is on card 2 at `/mnt/sdcard/Ports/SlayTheSpire`.
The card-1 menu entry forwards there. The previous card-1 directory is retained
as a backup, not used as the active save or cache directory.

The `p0-single-3` derived JAR retains LibGDX's required `libopenal.so` entry,
using the firmware OpenAL library instead of the upstream sndio-dependent one.
The original purchased JAR remains unchanged.

`run-java.sh` records the actual Java PID and exit code because the upstream
Weston wrapper exits zero even when Java aborts. A zero Java exit code alone
does not prove success: exceptions on the render thread may still exit zero.

When started through SSH, the firmware `dmenu.bin` may remain active, consume
input independently, and cover the game. The launcher pauses only running
`dmenu.bin` processes for the game session and resumes them during cleanup.
A PID/start-time checked watchdog restores them if the launcher disappears.
The compositor, audio service, and system configuration are left running.

## Input and swap timing

The launcher now starts PortMaster `gptokeyb` with the SDL mapping verified in
the local Balatro port, including b3/b2 for X/Y and b10/b11 for triggers.
`rgds-input-agent.jar` isolates directional arrow keys from trigger keys in
the upstream keyboard-to-controller bridge. It transforms classes in memory;
the purchased and cached game JARs are not rewritten.

Initial testing reached KeyboardBlocker but not game actions. Runtime
instrumentation measured approximately 1 second between render calls.
CardCrawlGame skips its update when raw delta exceeds 0.1 seconds. The Crusty
GLX swap-interval entry point is a no-op in this runtime. The small
`librgds-sdl.so` shim applies SDL swap interval 0 inside this process,
leaving the game's 24 FPS limiter enabled. The same scene then ran around
24 FPS with regular input updates. This is not a full gameplay benchmark.

`rgds_exit.py` discovers input nodes by name, monitors Back/Select/Guide and
the dedicated KEY_BACK, and triggers after a continuous 1.5-second hold.
It verifies Java's session arguments and PID birth time before TERM, with
KILL after 3 seconds if needed. Both normal Select exit and a SIGSTOP-hung
JVM exited during device tests, and the menu resumed without leftover
mapper/guard processes. Emergency exit does not promise an unsaved-game save.

Build the Java adapter with `python tools/build_input_agent.py` (JDK 11+).
Build the ARM64 shim with:

```sh
aarch64-linux-gnu-gcc -shared -fPIC -O2 -Wall -Wextra -Werror \
    -o platform/librgds-sdl.so platform/rgds_sdl.c -ldl
```

`tools/check_device_input.py` is an opt-in device-side synthetic regression,
not part of the distributed application. It requires the game and exit guard
to be running and the system menu absent or paused. It does not substitute
for pressing the physical buttons during gameplay.

## Save profile input

Opening RenamePopup installs TypeHelper as a new InputProcessor; closing it
installs ScrollInputProcessor. Upstream KeyboardBlocker only installed once,
so profile naming bypassed the virtual controller and even lost the release
of the A press that opened the popup. The input agent now wraps every
LwjglInput.setInputProcessor call, keeps the same keyboard state, and updates
the pointer delegate without recursive wrapping.

New profiles are prefilled as `RGDS 1`, `RGDS 2`, or `RGDS 3`; an existing
profile retains its name. Y uses the game's confirm action and B cancels.
There is no full on-screen keyboard in this version.

Device regression on initially empty profile preferences verified opening,
B cancellation without writing a name, A reopening, X/L/R without text
insertion, and Y confirmation persisting `PROFILE_NAME=RGDS 1`.
`tools/InputAgentTest.java` checks processor transitions, key releases,
pointer delegation, name defaults and both bytecode transformations using
the user's JAR solely as a local test dependency.
