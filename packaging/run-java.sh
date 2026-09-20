#!/bin/bash
set -u

# The wrapper's XWayland serves LWJGL's X11 calls. Crusty's actual SDL
# window must use the firmware compositor, not KMS/DRM or the dummy display.
if [ "${SLAYTHESPIRE_LAUNCH_MODE:-system-wayland}" = "system-wayland" ]; then
    export CRUSTY_WLMODE=1
    export CRUSTY_WLDISP="$SLAYTHESPIRE_PARENT_SOCKET"
    export WAYLAND_DISPLAY="$SLAYTHESPIRE_PARENT_SOCKET"
    export SDL_VIDEODRIVER=wayland
    export SDL_VIDEO_EGL_DRIVER=/usr/lib/libEGL.so.1
    export SDL_VIDEO_GL_DRIVER=/usr/lib/libGLESv2.so.2
fi

"$JAVA_HOME/bin/java" "$@" &
pid=$!
printf '%s\n' "$pid" >"$SLAYTHESPIRE_SESSION.java.pid"
trap 'kill -TERM "$pid" 2>/dev/null || true' TERM INT HUP
wait "$pid"
rc=$?
printf '%s\n' "$rc" >"$SLAYTHESPIRE_SESSION.java.rc"
echo "[java] exit_code=$rc"
exit "$rc"
