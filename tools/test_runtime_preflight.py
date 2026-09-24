"""Dependency failure injection in a shell fixture, never physical acceptance."""

from pathlib import Path
import shutil
import subprocess
import unittest

from assemble_r4_adapter_package import ADAPTER_SOURCES, generated_launcher

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "packaging/runtime_preflight.sh").read_text(encoding="utf-8")

SETUP = r'''
set -eu
fixture=$(mktemp -d /tmp/sts-preflight-test-XXXXXX)
trap 'rm -rf -- "$fixture"' EXIT
APP_DIR="$fixture/Slay the Spire for RGDSplus"
CONTROLFOLDER="$fixture/PortMaster"
SESSION="$fixture/session"
XDG_RUNTIME_DIR="$fixture"
WAYLAND_DISPLAY=wayland-test
SLAYTHESPIRE_LAUNCH_MODE=system-wayland
mkdir -p "$APP_DIR" "$CONTROLFOLDER/libs" "$fixture/java-seed/bin" "$fixture/weston-seed"
touch "$CONTROLFOLDER/control.txt" "$CONTROLFOLDER/gptokeyb" "$fixture/libopenal.so.1" "$fixture/wayland-test"
chmod +x "$CONTROLFOLDER/gptokeyb"
printf '#!/bin/sh\necho '\''openjdk version "17.0.13"'\'' >&2\n' >"$fixture/java-seed/bin/java"
printf '#!/bin/bash\nexit 0\n' >"$fixture/weston-seed/westonwrap.sh"
chmod +x "$fixture/java-seed/bin/java" "$fixture/weston-seed/westonwrap.sh"
java_name=zulu17.54.21-ca-jre17.0.13-linux
touch "$CONTROLFOLDER/libs/$java_name.squashfs" "$CONTROLFOLDER/libs/weston_pkg_0.2.squashfs"
fail_mount=""
mount() {
    printf 'mount %s\n' "$4" >>"$fixture/mount-events"
    case "$3" in
        *zulu*) [ "$fail_mount" != java ] || return 1; cp -R "$fixture/java-seed/." "$4/" ;;
        *weston*) [ "$fail_mount" != weston ] || return 1; cp -R "$fixture/weston-seed/." "$4/" ;;
        *) return 1 ;;
    esac
}
umount() {
    printf 'umount %s\n' "$1" >>"$fixture/mount-events"
    # Stand in for removing a mount, without removing the mountpoint.
    rm -rf -- "$1/bin" "$1/westonwrap.sh"
}
python3() { return 0; }
'''


@unittest.skipUnless(shutil.which("bash"), "bash required for dependency failure injection")
class RuntimePreflightTests(unittest.TestCase):
    def replay(self, changes="", expected=None, assertions=""):
        source = SOURCE.replace("/usr/lib/libopenal.so.1", "$fixture/libopenal.so.1")
        source = source.replace("/tmp/sts-preflight-XXXXXX", "$fixture/sts-preflight-XXXXXX")
        source = source.replace('[ ! -S "$path" ]', '[ ! -f "$path" ]')
        ending = r'''
rc=0
runtime_preflight || rc=$?
if [ "$rc" = 0 ]; then
    touch "$fixture/extraction-started"
fi
test -z "$(find "$fixture" -mindepth 1 -maxdepth 1 -type d -name 'sts-preflight-*')"
'''
        if expected is None:
            ending += 'test "$rc" = 0\ntest -f "$fixture/extraction-started"\n'
        else:
            ending += ('test "$rc" = 3\ntest ! -e "$fixture/extraction-started"\n'
                       f'grep -F "{expected}" "$SESSION.preflight.txt"\n')
        result = subprocess.run(
            ["bash", "-s"], input=(SETUP + source + changes + ending + assertions).encode("utf-8"),
            capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode("utf-8", errors="replace"))
        return result.stdout.decode("utf-8", errors="replace")

    def test_valid_images_execute_java_and_release_both_mounts(self):
        self.replay(assertions=r'''
test "$(grep -c '^mount ' "$fixture/mount-events")" = 2
test "$(grep -c '^umount ' "$fixture/mount-events")" = 2
grep '17.0.13' "$SESSION.java-check.txt"
''')

    def test_missing_portmaster(self):
        self.replay('rm "$CONTROLFOLDER/control.txt"\n', "PortMaster/control.txt")

    def test_missing_input_helper(self):
        self.replay('rm "$CONTROLFOLDER/gptokeyb"\n', "gptokeyb")

    def test_missing_python_modules(self):
        self.replay('python3() { return 1; }\n', "Python 3")

    def test_missing_audio_library(self):
        self.replay('rm "$fixture/libopenal.so.1"\n', "libopenal.so.1")

    def test_missing_display_socket(self):
        self.replay('rm "$fixture/wayland-test"\n', "显示服务不可用")

    def test_missing_java_image(self):
        self.replay('rm "$CONTROLFOLDER/libs/$java_name.squashfs"\n', "缺少 Java 17")

    def test_missing_weston_image(self):
        self.replay('rm "$CONTROLFOLDER/libs/weston_pkg_0.2.squashfs"\n', "缺少显示运行镜像")

    def test_bad_java_override_does_not_silently_fall_back(self):
        self.replay('SLAYTHESPIRE_JAVA_HOME="$fixture/missing-java"\n', "指定的 Java")

    def test_java_failure_releases_mount(self):
        self.replay(
            "printf '#!/bin/sh\\nexit 126\\n' >\"$fixture/java-seed/bin/java\"\n",
            "Java 无法运行",
            'test "$(grep -c \'^umount \' "$fixture/mount-events")" = 1\n',
        )

    def test_wrong_java_version(self):
        self.replay(
            """printf '#!/bin/sh\\necho '\\''openjdk version "21.0.1"'\\'' >&2\\n' >"$fixture/java-seed/bin/java"\n""",
            "Java 版本不匹配",
        )

    def test_bad_java_image(self):
        self.replay('fail_mount=java\n', "Java 镜像无法挂载")

    def test_bad_weston_image_releases_java(self):
        self.replay(
            'fail_mount=weston\n', "Weston 镜像无法挂载",
            'test "$(grep -c \'^umount \' "$fixture/mount-events")" = 1\n',
        )

    def test_incomplete_weston_image(self):
        self.replay('rm "$fixture/weston-seed/westonwrap.sh"\n', "westonwrap.sh")

    def test_directory_runtimes_need_no_mounts(self):
        self.replay(r'''
cp -R "$fixture/java-seed" "$CONTROLFOLDER/libs/$java_name"
cp -R "$fixture/weston-seed" "$CONTROLFOLDER/libs/weston_pkg_0.2"
''', assertions='test ! -e "$fixture/mount-events"\n')

    def offline_setup(self):
        return r'''
mkdir -p "$APP_DIR/runtime/offline"
cp "$CONTROLFOLDER/libs/"*.squashfs "$APP_DIR/runtime/offline/"
mkdir "$APP_DIR/runtime/offline/libs"
touch "$APP_DIR/runtime/offline/libs/libjpeg.so.8" "$APP_DIR/runtime/offline/libs/libXtst.so.6"
(cd "$APP_DIR/runtime/offline" && sha256sum *.squashfs libs/* >SHA256SUMS)
rm "$CONTROLFOLDER/libs/"*.squashfs
'''

    def test_offline_install_needs_no_shared_images(self):
        self.replay(self.offline_setup(), assertions=r'''
test "$(grep -c '^mount ' "$fixture/mount-events")" = 2
test "$(grep -c '^umount ' "$fixture/mount-events")" = 2
''')

    def test_corrupt_offline_image_stops_before_mount_or_extraction(self):
        self.replay(self.offline_setup() + r'''
printf 'broken' >>"$APP_DIR/runtime/offline/$java_name.squashfs"
''', "离线运行库缺失或校验失败",
                    'test ! -e "$fixture/mount-events"\n')

    def test_missing_one_offline_image_is_not_hidden_by_shared_install(self):
        self.replay(self.offline_setup() + r'''
cp "$APP_DIR/runtime/offline/"*.squashfs "$CONTROLFOLDER/libs/"
rm "$APP_DIR/runtime/offline/weston_pkg_0.2.squashfs"
''', "离线运行库缺失或校验失败")

    def test_missing_offline_checksums(self):
        self.replay(self.offline_setup() + r'''
rm "$APP_DIR/runtime/offline/SHA256SUMS"
''', "离线运行库缺失或校验失败")

    def test_missing_offline_native_library(self):
        self.replay(self.offline_setup() + r'''
rm "$APP_DIR/runtime/offline/libs/libjpeg.so.8"
''', "离线运行库缺失或校验失败")

    def test_missing_transitive_weston_dependency(self):
        self.replay(r'''
cp -R "$fixture/weston-seed" "$CONTROLFOLDER/libs/weston_pkg_0.2"
touch "$CONTROLFOLDER/libs/weston_pkg_0.2/wp_weston"
mkdir "$fixture/bin"
printf '#!/bin/sh\necho "libjpeg.so.8 => not found"\n' >"$fixture/bin/ldd"
chmod +x "$fixture/bin/ldd"
export PATH="$fixture/bin:$PATH"
''', "底层依赖不完整")

    def test_ldd_failure_is_not_ignored(self):
        self.replay(r'''
cp -R "$fixture/weston-seed" "$CONTROLFOLDER/libs/weston_pkg_0.2"
touch "$CONTROLFOLDER/libs/weston_pkg_0.2/wp_weston"
mkdir "$fixture/bin"
printf '#!/bin/sh\nexit 1\n' >"$fixture/bin/ldd"
chmod +x "$fixture/bin/ldd"
export PATH="$fixture/bin:$PATH"
''', "底层依赖不完整")

    def test_offline_images_precede_shared_runtime_directories(self):
        self.replay(self.offline_setup() + r'''
mkdir -p "$CONTROLFOLDER/libs/$java_name/bin" "$CONTROLFOLDER/libs/weston_pkg_0.2"
printf '#!/bin/sh\nexit 127\n' >"$CONTROLFOLDER/libs/$java_name/bin/java"
printf '#!/bin/bash\nthis is invalid (\n' >"$CONTROLFOLDER/libs/weston_pkg_0.2/westonwrap.sh"
chmod +x "$CONTROLFOLDER/libs/$java_name/bin/java" "$CONTROLFOLDER/libs/weston_pkg_0.2/westonwrap.sh"
''', assertions='test "$(grep -c \'^mount \' "$fixture/mount-events")" = 2\n')

    def test_firmware_notice_contains_report_and_has_bounded_lifetime(self):
        source = SOURCE.replace("/usr/bin/weston-terminal", "$fixture/terminal")
        source = source.replace("/tmp/sts-rgds-preflight-error-$$.sh", "$fixture/notice.sh")
        source = source.replace('[ -S "${XDG_RUNTIME_DIR}/${WAYLAND_DISPLAY}" ]', "true")
        script = SETUP + source + r'''
printf 'missing-runtime-detail\n' >"$SESSION.preflight.txt"
printf '#!/bin/sh\nexit 0\n' >"$fixture/terminal"
chmod +x "$fixture/terminal"
sleep() { :; }
show_preflight_failure
test -n "$NOTICE_PID"
wait "$NOTICE_PID"
export -f sleep
bash "$NOTICE_SCRIPT"
'''
        result = subprocess.run(["bash", "-s"], input=script.encode("utf-8"),
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"missing-runtime-detail", result.stdout)


class PreflightIntegrationTests(unittest.TestCase):
    def test_launch_and_preflight_use_same_offline_images(self):
        launcher = generated_launcher().decode("utf-8")
        self.assertIn('"$APP_DIR/runtime/offline/$JAVA_RUNTIME.squashfs"', launcher)
        self.assertIn('"$APP_DIR/runtime/offline/$WESTON_RUNTIME.squashfs"', launcher)
        self.assertNotIn("ROCreader_RGDSPlus", launcher)
        self.assertNotIn("harbourmaster", launcher)
        self.assertIn('mount -o ro "$JAVA_SQUASHFS"', launcher)
        self.assertIn('mount -o ro "$WESTON_SQUASHFS"', launcher)

    def test_check_precedes_hash_cache_validation_and_extraction(self):
        launcher = generated_launcher().decode("utf-8")
        at = launcher.index("if runtime_preflight; then")
        for marker in ("SOURCE_SHA=", "if ! cached_jar_is_valid;", 'if "$APP_DIR/patch_safe.sh"'):
            self.assertLess(at, launcher.index(marker))
        self.assertLess(launcher.index("trap 'stop_resource_notice;"), at)
        self.assertIn("show_preflight_failure\n    exit 3", launcher)
        self.assertIn("runtime_preflight.sh", ADAPTER_SOURCES)
        self.assertIn("runtime_preflight.sh",
                      (ROOT / "tools/assemble_package.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
