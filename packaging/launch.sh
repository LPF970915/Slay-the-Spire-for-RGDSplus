#!/bin/bash
set -u

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) || exit 1
export SLAYTHESPIRE_RGDS_ROOT="$APP_DIR"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/var/run}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_DATA_HOME="$APP_DIR/saves"
export XDG_CONFIG_HOME="$APP_DIR/saves"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-pulse}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/tmp/pulse-socket}"
export DISPLAY_WIDTH="${DISPLAY_WIDTH:-1024}"
export DISPLAY_HEIGHT="${DISPLAY_HEIGHT:-768}"
export DISPLAY_REFRESH="${DISPLAY_REFRESH:-60}"

LOCK_DIR="$APP_DIR/cache/.running"
mkdir -p "$APP_DIR/cache"
if [ -f "$LOCK_DIR/pid" ]; then
    LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[launcher] another instance is already running pid=$LOCK_PID"
        exit 4
    fi
    rm -rf "$LOCK_DIR"
fi
mkdir "$LOCK_DIR" 2>/dev/null || {
    echo "[launcher] failed to acquire single-instance lock"
    exit 4
}
printf '%s\n' "$$" >"$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

mkdir -p "$APP_DIR/logs" "$APP_DIR/saves" "$APP_DIR/cache/builds"
SESSION="$APP_DIR/logs/$(date +%Y%m%d-%H%M%S)-$$"
LOG="$SESSION.log"
printf '%s\n' "$LOG" > "$APP_DIR/logs/latest-path.txt"
exec >>"$LOG" 2>&1
cd "$APP_DIR" || exit 1

echo "[launcher] date=$(date -Iseconds)"
echo "[launcher] app=$APP_DIR"
echo "[launcher] firmware=$(uname -a)"
cat "$APP_DIR/build-manifest.json"

CONTROLFOLDER="${SLAYTHESPIRE_PORTMASTER:-}"
if [ -z "$CONTROLFOLDER" ]; then
    for candidate in \
        "/mnt/ports/PortMaster" \
        "/mnt/mmc/Ports/PortMaster" \
        "/mnt/mmc/Tools/PortMaster" \
        "/opt/system/Tools/PortMaster" \
        "/opt/tools/PortMaster" \
        "${XDG_DATA_HOME%/saves}/PortMaster" \
        "/roms/ports/PortMaster"; do
        if [ -f "$candidate/control.txt" ]; then
            CONTROLFOLDER="$candidate"
            break
        fi
    done
fi
echo "[launcher] controlfolder=${CONTROLFOLDER:-missing}"

if [ -n "$CONTROLFOLDER" ] && [ -f "$CONTROLFOLDER/control.txt" ]; then
    # shellcheck disable=SC1090
    # Some firmware PortMaster control files reference optional variables before
    # initializing them. Keep that compatibility layer outside nounset mode.
    set +u
    source "$CONTROLFOLDER/control.txt"
    set -u
    if type pm_platform_helper >/dev/null 2>&1; then
        pm_platform_helper java || true
    fi
fi

if [ ! -f "$APP_DIR/desktop-1.0.jar" ]; then
    echo "[launcher] missing user file: $APP_DIR/desktop-1.0.jar"
    if type pm_message >/dev/null 2>&1; then
        pm_message "Copy your purchased desktop-1.0.jar into the SlayTheSpire folder."
    fi
    exit 2
fi

SOURCE_SHA=$(sha256sum "$APP_DIR/desktop-1.0.jar" | awk '{print $1}')
BUILD_ID="${SOURCE_SHA}-p0-single-3"
BUILD_DIR="$APP_DIR/cache/builds/$BUILD_ID"
OUTPUT="$BUILD_DIR/desktoppatched.jar"
STAMP="$BUILD_DIR/ready.txt"

if [ ! -f "$OUTPUT" ] || [ ! -f "$STAMP" ] ||
   ! grep -qx "source_sha256=$SOURCE_SHA" "$STAMP"; then
    echo "[launcher] building patched jar; upstream warns first build may take about 15 minutes"
    TEMP_DIR="$APP_DIR/cache/.build-$BUILD_ID-$$"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR" "$BUILD_DIR"
    if "$APP_DIR/patch_safe.sh" "$APP_DIR/desktop-1.0.jar" \
        "$TEMP_DIR/desktoppatched.jar" "$TEMP_DIR"; then
        :
    else
        rc=$?
        echo "[launcher] patch failed rc=$rc; source jar was retained"
        rm -rf "$TEMP_DIR"
        exit "$rc"
    fi
    mv "$TEMP_DIR/desktoppatched.jar" "$OUTPUT"
    {
        echo "source_sha256=$SOURCE_SHA"
        echo "build_id=$BUILD_ID"
        echo "created=$(date -Iseconds)"
    } >"$TEMP_DIR/ready.txt"
    mv "$TEMP_DIR/ready.txt" "$STAMP"
    rm -rf "$TEMP_DIR"
else
    echo "[launcher] using cached $OUTPUT"
fi

printf '1024\n768\n24\nfalse\ntrue\nfalse\n' >"$APP_DIR/info.displayconfig"

JAVA_HOME="${SLAYTHESPIRE_JAVA_HOME:-}"
if [ -n "$JAVA_HOME" ] && [ ! -x "$JAVA_HOME/bin/java" ]; then
    echo "[launcher] invalid SLAYTHESPIRE_JAVA_HOME=$JAVA_HOME"
    exit 3
fi

JAVA_RUNTIME="zulu17.54.21-ca-jre17.0.13-linux"
JAVA_SQUASHFS=""
if [ -z "$JAVA_HOME" ]; then
    for candidate in \
        "$APP_DIR/runtime/java" \
        "${CONTROLFOLDER:+$CONTROLFOLDER/libs/$JAVA_RUNTIME}" \
        "${CONTROLFOLDER:+$CONTROLFOLDER/libs/$JAVA_RUNTIME.squashfs}"; do
        if [ -x "$candidate/bin/java" ]; then
            JAVA_HOME="$candidate"
            break
        elif [ -f "$candidate" ]; then
            JAVA_SQUASHFS="$candidate"
            break
        fi
    done
fi

MOUNTED_JAVA=0
MOUNTED_WESTON=0
WESTON_DIR=/tmp/weston-rgdsplus
WESTON_BRIDGE_DIR=/tmp/weston_runtime
WESTON_BRIDGE_READY=0
PARENT_WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
PARENT_WAYLAND_SOCKET="${XDG_RUNTIME_DIR}/${PARENT_WAYLAND_DISPLAY}"
export SLAYTHESPIRE_PARENT_SOCKET="$PARENT_WAYLAND_SOCKET"
export SLAYTHESPIRE_SESSION="$SESSION"
PAUSED_MENU_PIDS=()
PAUSED_MENU_STARTS=()
MENU_WATCHDOG=""
INPUT_PID=""
EXIT_GUARD_PID=""

resume_menu() {
    local index pid birth
    for index in "${!PAUSED_MENU_PIDS[@]}"; do
        pid=${PAUSED_MENU_PIDS[$index]}
        birth=$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null || true)
        if [ "$birth" = "${PAUSED_MENU_STARTS[$index]}" ]; then
            kill -CONT "$pid" 2>/dev/null || true
        fi
    done
}

pause_menu() {
    local pid state birth owner=$$ owner_birth
    # SSH testing leaves the firmware menu alive. Normal menu-launched ports
    # have no dmenu process here, so this guard is a no-op in that workflow.
    for pid in $(pgrep -x dmenu.bin 2>/dev/null || true); do
        state=$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || true)
        [ "$state" != T ] && [ "$state" != t ] || continue
        birth=$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null || true)
        [ -n "$birth" ] || continue
        if kill -STOP "$pid" 2>/dev/null; then
            PAUSED_MENU_PIDS+=("$pid")
            PAUSED_MENU_STARTS+=("$birth")
            echo "[launcher] paused firmware menu pid=$pid"
        fi
    done
    if [ "${#PAUSED_MENU_PIDS[@]}" -gt 0 ]; then
        owner_birth=$(awk '{print $22}' "/proc/$owner/stat")
        (
            trap - EXIT TERM INT HUP
            while [ "$(awk '{print $22}' "/proc/$owner/stat" 2>/dev/null)" = "$owner_birth" ]; do
                sleep 2
            done
            resume_menu
        ) &
        MENU_WATCHDOG=$!
    fi
}
if [ -z "$JAVA_HOME" ] && [ -n "$JAVA_SQUASHFS" ]; then
    JAVA_HOME=/tmp/javaruntime-rgdsplus
    mkdir -p "$JAVA_HOME"
    if mountpoint -q "$JAVA_HOME" 2>/dev/null &&
       [ -x "$JAVA_HOME/bin/java" ]; then
        echo "[launcher] java runtime already mounted at $JAVA_HOME"
    else
        if mountpoint -q "$JAVA_HOME" 2>/dev/null; then
            echo "[launcher] clearing stale Java runtime mount at $JAVA_HOME"
            ${ESUDO:-} umount "$JAVA_HOME" || {
                echo "[launcher] failed to clear stale Java runtime mount"
                exit 3
            }
        fi
        MOUNT_CMD="${ESUDO:-}"
        $MOUNT_CMD mount "$JAVA_SQUASHFS" "$JAVA_HOME" || {
            echo "[launcher] failed to mount Java runtime"
            exit 3
        }
        MOUNTED_JAVA=1
    fi
fi

cleanup() {
    for helper in "$INPUT_PID" "$EXIT_GUARD_PID"; do
        if [ -n "$helper" ]; then
            kill -TERM "$helper" 2>/dev/null || true
            wait "$helper" 2>/dev/null || true
        fi
    done
    resume_menu
    if [ -n "$MENU_WATCHDOG" ]; then
        kill "$MENU_WATCHDOG" 2>/dev/null || true
        wait "$MENU_WATCHDOG" 2>/dev/null || true
    fi
    if mountpoint -q /tmp/javaruntime-rgdsplus 2>/dev/null; then
        ${ESUDO:-} umount /tmp/javaruntime-rgdsplus || true
    fi
    if mountpoint -q "$WESTON_DIR" 2>/dev/null; then
        ${ESUDO:-} umount "$WESTON_DIR" || true
    fi
    if [ "$WESTON_BRIDGE_READY" -eq 1 ]; then
        rm -f \
            "$WESTON_BRIDGE_DIR/$PARENT_WAYLAND_DISPLAY" \
            "$WESTON_BRIDGE_DIR/wayland-5" \
            "$WESTON_BRIDGE_DIR/wayland-5.lock" \
            "$WESTON_BRIDGE_DIR/wayland-0.lock"
        rmdir "$WESTON_BRIDGE_DIR" 2>/dev/null || true
    fi
}
trap 'cleanup; rm -rf "$LOCK_DIR"' EXIT

if [ -z "$JAVA_HOME" ] || [ ! -x "$JAVA_HOME/bin/java" ]; then
    echo "[launcher] Java 17 runtime not found"
    echo "[launcher] install $JAVA_RUNTIME.squashfs through PortMaster or set SLAYTHESPIRE_JAVA_HOME"
    exit 3
fi

export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$APP_DIR:$JAVA_HOME/lib:$JAVA_HOME/lib/server:/mnt/ports/PortMaster/libs:/mnt/mmc/Roms/APPS/ROCreader_RGDSPlus/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}:/usr/lib:/lib"
export WRAPPED_LIBRARY_PATH="$APP_DIR"
export WRAPPED_PRELOAD="$APP_DIR/librgds-sdl.so:$APP_DIR/libwrap.so"
export LIBGL_ES="${LIBGL_ES:-3}"
export LIBGL_MIPMAP="${LIBGL_MIPMAP:-3}"
export LIBGL_FORCE16BITS="${LIBGL_FORCE16BITS:-1}"
export TEXCOMPRESS_FORCE="${TEXCOMPRESS_FORCE:-astc}"
case "$TEXCOMPRESS_FORCE" in
    astc) TEXTURE_CACHE_DEFAULT="$APP_DIR/cache/texcache" ;;
    etc2) TEXTURE_CACHE_DEFAULT="$APP_DIR/cache/texcache-etc2" ;;
    *) echo "[launcher] unsupported texture format: $TEXCOMPRESS_FORCE"; exit 3 ;;
esac
export CRUSTY_BLOCK_INPUT="${CRUSTY_BLOCK_INPUT:-1}"

# LWJGL 2 looks for the exact libopenal.so filename in its native library
# path. The device filesystem does not support symlinks, so stage a local
# copy of the firmware's versioned system library at launch time.
if [ ! -f "$APP_DIR/libopenal.so" ]; then
    cp -fL /usr/lib/libopenal.so.1 "$APP_DIR/libopenal.so" || {
        echo "[launcher] failed to stage system OpenAL"
        exit 3
    }
fi

XMX="${SLAYTHESPIRE_XMX:-140M}"
LAUNCH_MODE="${SLAYTHESPIRE_LAUNCH_MODE:-system-wayland}"
export SLAYTHESPIRE_LAUNCH_MODE="$LAUNCH_MODE"
echo "[launcher] java=$JAVA_HOME/bin/java"
echo "[launcher] mode=$LAUNCH_MODE"
echo "[launcher] source_sha256=$SOURCE_SHA"

JAVA_ARGS=(
    "-javaagent:$APP_DIR/controller-injector.jar"
    "-javaagent:$APP_DIR/rgds-input-agent.jar"
    "-javaagent:$APP_DIR/texcompress-agent.jar=native=$APP_DIR/libtexcompress.so"
    "-Dtexcompress.scale=1"
    "-Dtexcompress.disable=${RGDS_DISABLE_COMPRESSION:-auto}"
    "-Dtexcompress.cache=${RGDS_TEXTURE_CACHE:-$TEXTURE_CACHE_DEFAULT}"
    "-Dsts.width=1024"
    "-Dsts.height=768"
    "-Dfont.multiplier=1.6"
    "-Dorg.lwjgl.opengl.Window.undecorated=true"
    "-Djava.library.path=$APP_DIR:/usr/lib:/lib"
    "-XX:ErrorFile=$SESSION.hs_err_%p.log"
    "-Xms128M"
    "-Xmx$XMX"
    "-Xss512k"
    "-XX:MaxDirectMemorySize=60M"
    "-XX:+UnlockExperimentalVMOptions"
    "-XX:+UseSerialGC"
    "-jar"
    "$OUTPUT"
)

run_game() {
    if [ "$LAUNCH_MODE" = "system-wayland" ] ||
       [ "$LAUNCH_MODE" = "nested-wayland" ] ||
       [ "$LAUNCH_MODE" = "upstream-weston" ]; then
        WESTON_RUNTIME="weston_pkg_0.2"
        WESTON_SQUASHFS=""
        for candidate in \
            "${CONTROLFOLDER:+$CONTROLFOLDER/libs/$WESTON_RUNTIME}" \
            "${CONTROLFOLDER:+$CONTROLFOLDER/libs/$WESTON_RUNTIME.squashfs}"; do
            if [ -x "$candidate/westonwrap.sh" ]; then
                WESTON_DIR="$candidate"
                break
            elif [ -f "$candidate" ]; then
                WESTON_SQUASHFS="$candidate"
                break
            fi
        done
        if [ -n "$WESTON_SQUASHFS" ] && [ ! -x "$WESTON_DIR/westonwrap.sh" ]; then
            mkdir -p "$WESTON_DIR"
            ${ESUDO:-} mount "$WESTON_SQUASHFS" "$WESTON_DIR" || {
                echo "[launcher] failed to mount Weston diagnostic runtime"
                return 3
            }
            MOUNTED_WESTON=1
        fi
        if [ ! -x "$WESTON_DIR/westonwrap.sh" ]; then
            echo "[launcher] Weston diagnostic runtime not found"
            return 3
        fi
        if [ "$LAUNCH_MODE" = "nested-wayland" ]; then
            "$WESTON_DIR/westonwrap.sh" wayland gl kiosk crusty_glx_gl4es \
                PATH="$PATH" JAVA_HOME="$JAVA_HOME" \
                XDG_DATA_HOME="$APP_DIR/saves" WAYLAND_DISPLAY= \
                /bin/bash "$APP_DIR/run-java.sh" "${JAVA_ARGS[@]}"
        else
            WESTON_HEADLESS_WIDTH=1024 \
            WESTON_HEADLESS_HEIGHT=768 \
            "$WESTON_DIR/westonwrap.sh" headless noop kiosk crusty_glx_gl4es \
                PATH="$PATH" JAVA_HOME="$JAVA_HOME" \
                XDG_DATA_HOME="$APP_DIR/saves" WAYLAND_DISPLAY= \
                /bin/bash "$APP_DIR/run-java.sh" "${JAVA_ARGS[@]}"
        fi
        return $?
    fi
    /bin/bash "$APP_DIR/run-java.sh" "${JAVA_ARGS[@]}"
}

if [ "$LAUNCH_MODE" = "system-wayland" ] && [ ! -S "$PARENT_WAYLAND_SOCKET" ]; then
    echo "[launcher] parent Wayland socket not found: $PARENT_WAYLAND_SOCKET"
    exit 3
fi

if [ "$LAUNCH_MODE" = "nested-wayland" ]; then
    if [ ! -S "$PARENT_WAYLAND_SOCKET" ]; then
        echo "[launcher] parent Wayland socket not found: $PARENT_WAYLAND_SOCKET"
        exit 3
    fi
    if [ -L "$WESTON_BRIDGE_DIR" ]; then
        echo "[launcher] refusing symlink runtime directory: $WESTON_BRIDGE_DIR"
        exit 3
    fi
    mkdir -p "$WESTON_BRIDGE_DIR"
    chmod 700 "$WESTON_BRIDGE_DIR"
    rm -f \
        "$WESTON_BRIDGE_DIR/$PARENT_WAYLAND_DISPLAY" \
        "$WESTON_BRIDGE_DIR/wayland-5" \
        "$WESTON_BRIDGE_DIR/wayland-5.lock" \
        "$WESTON_BRIDGE_DIR/wayland-0.lock"
    ln -s "$PARENT_WAYLAND_SOCKET" \
        "$WESTON_BRIDGE_DIR/$PARENT_WAYLAND_DISPLAY"
    WESTON_BRIDGE_READY=1
    export WRAPPED_LIBRARY_PATH="$APP_DIR:$JAVA_HOME/lib:$JAVA_HOME/lib/server:/mnt/ports/PortMaster/libs:/mnt/mmc/Roms/APPS/ROCreader_RGDSPlus/lib:/usr/lib:/lib"
fi

pause_menu
if ! command -v python3 >/dev/null 2>&1 ||
   [ ! -x "$CONTROLFOLDER/gptokeyb" ]; then
    echo "[launcher] input requires python3 and PortMaster/gptokeyb"
    exit 3
fi
python3 "$APP_DIR/rgds_exit.py" --session "$SESSION" --owner "$$" &
EXIT_GUARD_PID=$!
for attempt in $(seq 1 40); do
    [ ! -f "$SESSION.exit-ready" ] || break
    kill -0 "$EXIT_GUARD_PID" 2>/dev/null || break
    sleep 0.05
done
if [ ! -f "$SESSION.exit-ready" ]; then
    echo "[launcher] long-press exit guard did not find the RGDSplus buttons"
    exit 3
fi
export SDL_GAMECONTROLLERCONFIG
SDL_GAMECONTROLLERCONFIG=$(cat "$APP_DIR/rgds-gamecontroller.txt")
export SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1
env -u LD_PRELOAD LD_LIBRARY_PATH=/usr/lib:/lib SDL_VIDEODRIVER=dummy \
    "$CONTROLFOLDER/gptokeyb" java -c "$APP_DIR/slay.gptk" &
INPUT_PID=$!
sleep 0.2
if ! kill -0 "$INPUT_PID" 2>/dev/null; then
    echo "[launcher] gamepad mapper failed to start"
    exit 3
fi
echo "[launcher] input mapper pid=$INPUT_PID exit guard pid=$EXIT_GUARD_PID"
run_game &
GAME_PID=$!
printf '%s\n' "$GAME_PID" >"$APP_DIR/logs/game.pid"

(
    while :; do
        pid="${GAME_PID:-}"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            printf '\n[resources] %s\n' "$(date -Iseconds)"
            java_pid=$(cat "$SESSION.java.pid" 2>/dev/null || true)
            if [ -n "$java_pid" ] && [ -r "/proc/$java_pid/status" ]; then
                echo "java_pid=$java_pid"
                awk '/^(VmRSS|VmHWM|VmSize|Threads):/ {print}' "/proc/$java_pid/status"
            fi
            awk '/^(MemAvailable|SwapFree):/ {print}' /proc/meminfo
        else
            break
        fi
        sleep 10
    done
) >>"$SESSION.resources.log" 2>&1 &
MONITOR_PID=$!

stop_game() {
    python3 "$APP_DIR/rgds_exit.py" --session "$SESSION" --stop || true
    wait "$GAME_PID" 2>/dev/null || true
}
trap stop_game TERM INT HUP

set +e
wait "$GAME_PID"
RC=$?
if [ -f "$SESSION.java.rc" ]; then
    RC=$(cat "$SESSION.java.rc")
elif [ "$RC" -eq 0 ]; then
    echo "[launcher] missing Java exit status; wrapper did not finish the game"
    RC=3
fi
set -e
kill "$MONITOR_PID" 2>/dev/null || true
wait "$MONITOR_PID" 2>/dev/null || true

echo "[launcher] java_exit_rc=$RC date=$(date -Iseconds)"
if [ "$RC" -ne 0 ]; then
    {
        echo "exit_code=$RC"
        tail -120 "$LOG"
        echo "[kernel tail]"
        dmesg | tail -80
    } >"$SESSION.crash.txt" 2>&1
fi

if type pm_finish >/dev/null 2>&1; then
    pm_finish
fi
exit "$RC"
