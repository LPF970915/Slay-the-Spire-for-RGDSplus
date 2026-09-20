# Slay the Spire for RGDSplus

This is a game-free RGDSplus adapter for the Steam/desktop release of Slay the
Spire. The purchased `desktop-1.0.jar` is supplied by the user and is never
committed, packaged, publicly uploaded, modified in place, or deleted.

The first milestone is a stable single-screen 1024x768 port on RGDSplus.
Dual-screen layout work is intentionally deferred until the single-screen
runtime, audio, saves, and scene transitions have been verified.

## Plan and acceptance

- [Complete porting plan (Chinese)](docs/RGDSPLUS_PORT_MASTER_PLAN.zh-CN.md)
- [Acceptance matrix and evidence status (Chinese)](docs/RGDSPLUS_ACCEPTANCE_MATRIX.zh-CN.md)
- [Native 4:3 rendering fix and verification limits (Chinese)](docs/RENDER_FIX_20260920.zh-CN.md)
- [Dual-screen interface allocation and cross-screen targeting research (Chinese)](docs/DUAL_SCREEN_INTERFACE_RESEARCH.zh-CN.md)
- [P0 dual-screen design review and gap checklist (Chinese)](docs/P0_DUAL_SCREEN_DESIGN.zh-CN.md)
- [P1 standalone geometry prototype and device evidence (Chinese)](docs/P1_GEOMETRY_PROTOTYPE.zh-CN.md)
- [R1 frozen geometry baseline and deferred work (Chinese)](docs/R1_CLOSEOUT.zh-CN.md)
- [R2 output and touch accuracy verification (Chinese)](docs/R2_TOUCH_PROBE.zh-CN.md)
- [R3 native dual-screen UI and device screenshots (Chinese)](docs/R3_NATIVE_UI.zh-CN.md)
- [Frozen R3 baseline and non-destructive rollback (Chinese)](docs/R3_BASELINE_20260920.zh-CN.md)
- [R3 complete backgrounds and small-screen revision (Chinese)](docs/R3_SMALL_SCREEN.zh-CN.md)
- [R3 30 FPS profiling and remaining transition stalls (Chinese)](docs/R3_PERFORMANCE.zh-CN.md)
- [Physically verified touch integration contract (Chinese)](docs/RGDSPLUS_TOUCH_CONTRACT.zh-CN.md)

The user confirmed single-screen stability on September 20, 2026 and authorized
dual-screen research. The preferred design puts combat visuals on the upper
screen and interactive controls on the lower screen, with directional touch
targeting and the existing controller fallback. Research authorization does not
mark unexecuted acceptance tests as passed. The stable installed runtime remains
single-screen. An isolated, game-free dual-screen geometry probe lives in
`prototype/p1/`; it is not integrated into the game.
The original top toolbar stays on the upper screen with controller navigation.
Lower-screen views reuse native background layers; migrated combat foreground
decorations appear only on the lower screen. The user approved P0 and explicitly
authorized P1 on September 20, 2026. The probe has its own card-2 menu entry,
directory, and logs and does not read or modify game saves.
R1 is now frozen at aim3 for its geometry scope. Final artwork and feel are
deferred to real-game integration. R2 is a separate silent card-2 probe for
output identity, raw touch accuracy, and lifecycle recovery; physical accuracy
and long-run acceptance remain explicitly separate from software tests.
The user subsequently authorized remote continuation into real-game UI.
`prototype/r3/` now provides a separate silent card-2 native UI candidate:
upper combat/top bar, lower hand/controls/background, native controller targeting,
and cross-screen arrow rendering. Touch is capture-only pending actual game
hitbox integration. This does not mark the remaining R2 physical tests passed.

## Local source

The current private test source is:

`D:\Program Files\Steam\steamapps\common\SlayTheSpire\desktop-1.0.jar`

The packaging tools accept an explicit path, but only copy or read it into a
temporary build cache. They do not add it to this repository.

## Project boundaries

- `upstream/` contains immutable PortMaster adapter files and checksums.
- `platform/` contains RGDSplus-specific launch and safe-patching logic.
- `packaging/` contains the game-free device package entrypoint and install notes.
- `tools/` contains source fetching, package assembly, and static checks.
- `prototype/p1/` contains the standalone silent dual-screen geometry probe.
- `prototype/r2/` contains the isolated output/touch measurement probe.
- `prototype/r3/` contains the isolated real-game UI routing adapter, without assets.
- `private/`, `cache/`, `saves/`, and device logs are ignored.

## Build

Fetch the fixed upstream PortMaster snapshot, then assemble a game-free package:

```powershell
py -3 tools/fetch_upstream.py
$env:JAVA_HOME = "C:\Program Files\Java\jdk-25"
py -3 tools/build_input_agent.py
# Build platform/librgds-sdl.so with an ARM64 Linux cross-compiler.
py -3 tools/assemble_package.py
py -3 tools/test_package.py
```

The SDL shim build uses `aarch64-linux-gnu-gcc -shared -fPIC -O2 -Wall
-Wextra -Werror -o platform/librgds-sdl.so platform/rgds_sdl.c -ldl`
from the repository root in Linux/WSL. Set `JAVA_HOME` to the installed JDK.

The result is written below `dist/Ports/`. It does not contain
`desktop-1.0.jar`.

For a private local device test, provide the game file separately. The
deployment tool never puts it in the package:

```powershell
$env:RGDSPLUS_SSH_PASSWORD = "..."
python tools/deploy_p0.py --game "D:\Program Files\Steam\steamapps\common\SlayTheSpire\desktop-1.0.jar" --launch
```

The password environment variable is optional; without it the tool prompts.
Do not commit the password or the deployed game file.

## Device install

Copy the generated `Ports/` directory to the device's `/mnt/sdcard/Ports/`
(card 2). Card 1 (`/mnt/mmc/Ports/`) is also supported.
Copy your own `desktop-1.0.jar` into the installed `SlayTheSpire/` directory.
Launch `Slay the Spire for RGDSplus.sh`.

The launcher uses the PortMaster Weston wrapper runtime by default so the
desktop LWJGL build gets an XWayland/GL4ES-compatible display. Crusty's SDL
window connects directly to the firmware Wayland socket, while the auxiliary
headless XWayland handles LWJGL's X11 calls. It does not
alter the device tree, install udev rules, or change the touchscreen mode.

Deployment defaults to card 2; select `--remote-ports /mnt/mmc/Ports` for card 1.
After the initial private upload, omit `--game` to update only the adapter.
The private test device's original card-1 entry now forwards to card 2 using
`packaging/card1-forwarder.sh`. Removing card 2 makes that entry fail explicitly;
it does not start an older card-1 copy or split saves across cards.
