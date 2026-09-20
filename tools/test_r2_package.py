"""R2 safety checks without touching a device or changing the frozen R1."""

import ast
import hashlib
import json
from pathlib import Path
import zipfile

from test_touch_contract import functions, calls

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "prototype/r2"
P1 = ROOT / "prototype/p1"


def main():
    fn = functions(HERE / "supervisor.py")
    main_fn, recover = fn["main"], fn["recover"]
    read = calls(main_fn, "read_mode")[0].lineno
    enable = calls(main_fn, "enable_mode")[0].lineno
    assert any(read < c.lineno < enable for c in calls(main_fn, "replace"))
    spawns = calls(main_fn, "Popen")
    assert spawns[0].lineno < read < enable < spawns[1].lineno
    for spawn in spawns:
        assert "pass_fds" in [k.arg for k in spawn.keywords]
    finalizers = [n for n in ast.walk(main_fn) if isinstance(n, ast.Try) and n.finalbody]
    assert any(any(calls(n, "restore_mode") for n in f.finalbody) for f in finalizers)
    assert calls(recover, "restore_mode")
    assert "SlayTheSpireGeometryP1" in (HERE / "supervisor.py").read_text()
    with zipfile.ZipFile(ROOT / "dist/SlayTheSpire_R2_TouchProbe_game-free.zip") as archive:
        prefix = "Ports/SlayTheSpireTouchR2/"
        manifest = json.loads(archive.read(prefix + "manifest.json"))
        assert manifest["game_assets"] is False
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(prefix + name)).hexdigest() == expected
        for name in ("touch_mode.py", "device_input.py", "launch.sh", "geometry.py"):
            assert archive.read(prefix + name) == (P1 / name).read_bytes()
        assert archive.read(prefix + "p1_display.py") == (P1 / "app.py").read_bytes()
        assert archive.read(prefix + "session_runtime.py") == (P1 / "supervisor.py").read_bytes()
        expected_names = {prefix + name for name in manifest["files"]}
        expected_names.update((prefix + "manifest.json", "Ports/Slay the Spire R2 Touch Probe.sh"))
        assert set(archive.namelist()) == expected_names
        for name in ("app.py", "probe.py", "supervisor.py", "README.zh-CN.md"):
            assert archive.read(prefix + name) == (HERE / name).read_bytes()
        assert all(not n.endswith((".jar", ".love", ".exe")) for n in archive.namelist())
    print("R2 package, lifecycle ordering and byte-identical touch helpers passed")


if __name__ == "__main__":
    main()
