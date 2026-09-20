#!/bin/bash
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/java/bin"

# A fake JVM verifies the post-wrapper environment and exit-status transport.
cat >"$WORK/java/bin/java" <<'JAVA'
#!/bin/bash
test "$CRUSTY_WLMODE" = 1 || exit 91
test "$WAYLAND_DISPLAY" = "$SLAYTHESPIRE_PARENT_SOCKET" || exit 92
test "$CRUSTY_WLDISP" = "$SLAYTHESPIRE_PARENT_SOCKET" || exit 93
test "$SDL_VIDEODRIVER" = wayland || exit 94
test "$1" = 'argument with spaces' || exit 95
exit "$FAKE_RC"
JAVA
chmod +x "$WORK/java/bin/java"
export JAVA_HOME="$WORK/java"
export SLAYTHESPIRE_SESSION="$WORK/session"
export SLAYTHESPIRE_PARENT_SOCKET=/var/run/wayland-0
export SLAYTHESPIRE_LAUNCH_MODE=system-wayland
for expected in 0 7 134; do
    export FAKE_RC="$expected"
    rc=0
    bash "$ROOT/packaging/run-java.sh" 'argument with spaces' || rc=$?
    test "$rc" -eq "$expected"
    test "$(cat "$WORK/session.java.rc")" -eq "$expected"
    test -s "$WORK/session.java.pid"
done
echo "launcher environment and exit-status tests passed"
