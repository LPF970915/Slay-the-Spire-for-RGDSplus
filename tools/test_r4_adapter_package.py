"""Static tests for the public R4 adapter-only package."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from assemble_r4_adapter_package import (
    ENTRY,
    PREFIX,
    ADAPTER_SOURCES,
    build,
    entry_bytes,
    generated_game_launcher,
    generated_launcher,
    validate_names,
    verify_archive,
)


class R4AdapterPackageTests(unittest.TestCase):
    def test_archive_rejects_game_and_player_payloads(self):
        for name in (
            PREFIX + "desktop-1.0.jar",
            PREFIX + "saves/IRONCLAD.autosave",
            PREFIX + "betaPreferences/STSSaveSlots",
            PREFIX + "logs/state.xml",
            "Ports/SlayTheSpire/supervisor.py",
            "../escape",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_names([name])

    def test_entry_and_launcher_are_public_safe(self):
        entry = entry_bytes().decode("utf-8")
        launcher = generated_launcher().decode("utf-8")
        self.assertEqual(PREFIX, "Ports/Slay the Spire for RGDSplus/")
        self.assertIn('"$PORTS/Slay the Spire for RGDSplus/supervisor.py"', entry)
        self.assertNotIn("SlayTheSpireDualR4", entry)
        self.assertNotIn("Slay the Spire for RGDSplus/supervisor.py", launcher)
        self.assertIn('"-javaagent:$APP_DIR/rgds-dual-r3.jar"', launcher)
        self.assertIn("$APP_DIR/librgds-dual.so:$APP_DIR/libwrap.so", launcher)
        self.assertIn('"$APP_DIR/run-java.sh" "${JAVA_ARGS[@]}"', launcher)
        self.assertIn("cd /tmp || exit 1", launcher)
        self.assertIn('exec "$WESTON_DIR/westonwrap.sh" headless noop kiosk crusty_glx_gl4es "$WESTON_COMMAND"', launcher)
        self.assertIn("unset WRAPPED_PRELOAD", launcher)
        self.assertIn("正在释放资源，请不要关机。", launcher)
        self.assertIn("数据仍在刷新，心跳", launcher)
        self.assertIn("纹理缓存：%s 个文件", launcher)
        self.assertIn("最近 15 秒计数未变化", launcher)
        self.assertIn("notice stays until the game draws", launcher)
        self.assertIn(r'\[rgds-r3\] frames=', launcher)
        self.assertIn("cached_jar_is_valid", launcher)
        self.assertIn("unzip -tq \"$OUTPUT\"", launcher)
        self.assertIn("TEXTURE_CACHE_READY", launcher)
        self.assertIn("texture cache is incomplete", launcher)
        self.assertIn("texture cache ready after first frame", launcher)
        self.assertIn("cleanup_stale_texture_temps", launcher)
        self.assertIn('PRELOAD_DIR=/tmp/sts-rgds-preload-', launcher)
        self.assertIn('ln -sf %q "$PRELOAD_DIR/libwrap.so"', launcher)
        self.assertEqual(generated_game_launcher(), generated_launcher())
        self.assertNotIn("runtime/PortMaster", entry)
        self.assertEqual(ENTRY, "Ports/Slay the Spire for RGDSplus.sh")
        self.assertNotIn("R4 All Pages", ENTRY)

    def test_cold_install_tools_match_patcher_paths(self):
        self.assertIn("tools/xdelta3", ADAPTER_SOURCES)
        self.assertNotIn("xdelta3", ADAPTER_SOURCES)
        patcher = ADAPTER_SOURCES["patch_safe.sh"].read_text(encoding="utf-8")
        self.assertIn('"$GAMEDIR/tools/xdelta3"', patcher)
        self.assertIn("[release] phase=extract-assets", patcher)
        self.assertIn("[release] phase=verify-archive", patcher)
        ogg = (Path(__file__).resolve().parents[1] / "upstream/slaythespire/tools/ogg.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("[release] audio {index}/{total}", ogg)

    def test_notice_owner_survives_patch_to_game_transition(self):
        launcher = generated_launcher().decode("utf-8")
        prefix, rest = launcher.split("start_resource_notice() {", 1)
        self.assertIn('NOTICE_PID=""', prefix)
        self.assertIn('NOTICE_SCRIPT=""', prefix)
        after_build = launcher.split("PAUSED_MENU_PIDS=()", 1)[1]
        self.assertNotIn('NOTICE_PID=""', after_build)
        self.assertNotIn('NOTICE_SCRIPT=""', after_build)
        self.assertIn('kill -0 "$NOTICE_PID"', rest)
        self.assertIn('while kill -0 "$GAME_PID"', rest)
        self.assertNotIn('while kill -0 "$notice_pid"', rest)
        self.assertIn('NOTICE_WATCHER=$!', rest)
        self.assertIn('kill -0 "$OWNER"', rest)
        self.assertLess(launcher.index("trap 'stop_resource_notice;"),
                        launcher.index("SOURCE_SHA="))

    @unittest.skipUnless(shutil.which("bash"), "bash required for notice lifecycle replay")
    def test_notice_is_singleton_and_closes_on_first_frame(self):
        launcher = generated_launcher().decode("utf-8")
        functions = launcher.split("start_resource_notice() {", 1)[1].split(
            "# Resource extraction precedes", 1)[0]
        functions = "start_resource_notice() {" + functions
        functions = functions.replace("/usr/bin/weston-terminal", '"$fixture/terminal"')
        # Only the compositor availability checks are replaced, not lifecycle code.
        functions = functions.replace('[ -S "${XDG_RUNTIME_DIR:-/var/run}/${WAYLAND_DISPLAY}" ]',
                                      "true")
        script = r'''
set -eu
fixture=$(mktemp -d /tmp/sts-notice-test-XXXXXX)
trap 'stop_resource_notice; rm -rf -- "$fixture"' EXIT
LOG="$fixture/game.log"
TEXTURE_CACHE_DEFAULT="$fixture/cache"
NOTICE_PID="" NOTICE_SCRIPT="" NOTICE_WATCHER=""
WAYLAND_DISPLAY=test
mkdir "$TEXTURE_CACHE_DEFAULT"
touch "$LOG"
printf '#!/bin/sh\nexec sleep 30\n' >"$fixture/terminal"
chmod +x "$fixture/terminal"
''' + functions + r'''
start_resource_notice
first=$NOTICE_PID
script=$NOTICE_SCRIPT
start_resource_notice
test "$NOTICE_PID" = "$first"
test -f "$script"
printf '[rgds-r3] frames=10 updates=10\n' >>"$LOG"
timeout 3 sh "$script"
stop_resource_notice
test -z "$NOTICE_PID"
test ! -f "$script"
if kill -0 "$first" 2>/dev/null; then exit 9; fi
echo 'notice lifecycle passed'
'''
        result = subprocess.run(["bash", "-s"], input=script.encode("utf-8"),
                                capture_output=True, timeout=35)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b"notice lifecycle passed", result.stdout)

    def test_fresh_archive_has_jvm_launcher_and_executable_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            path = build(Path(directory) / "adapter.zip")
            verify_archive(path)
            with zipfile.ZipFile(path) as archive:
                launcher = archive.read(PREFIX + "game-launch.sh")
                self.assertEqual(launcher, generated_launcher())
                self.assertNotIn(b"Slay the Spire for RGDSplus/supervisor.py", launcher)
                for tool in ("xdelta3", "oggenc", "oggdec"):
                    name = PREFIX + "tools/" + tool
                    self.assertEqual(archive.read(name)[:4], b"\x7fELF")
                    self.assertTrue(archive.getinfo(name).external_attr >> 16 & 0o111)

    def test_built_archive_has_no_game_jar_when_present(self):
        archive_path = Path(__file__).resolve().parents[1] / (
            "dist/Slay the Spire for RGDSplus.zip"
        )
        if not archive_path.exists():
            self.skipTest("adapter archive has not been built")
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            self.assertIn(ENTRY, names)
            self.assertIn(PREFIX + "rgds-dual-r3.jar", names)
            self.assertNotIn(PREFIX + "desktop-1.0.jar", names)
            self.assertNotIn("Ports/Slay the Spire R4 All Pages.sh", names)


if __name__ == "__main__":
    unittest.main()
