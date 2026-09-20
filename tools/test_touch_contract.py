"""Guard the proven P1 touch lifecycle and shipping contents against omissions."""

import ast
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
P1 = ROOT / "prototype/p1"


def functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body
            if isinstance(node, ast.FunctionDef)}


def calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and
            ((isinstance(n.func, ast.Name) and n.func.id == name) or
             (isinstance(n.func, ast.Attribute) and n.func.attr == name))]


def validate_source(directory=P1):
    fn = functions(directory / "supervisor.py")
    main, recover = fn["main"], fn["recover"]
    read = calls(main, "read_mode")[0]
    enable = calls(main, "enable_mode")[0]
    persist = [n for n in calls(main, "replace")
               if read.lineno < n.lineno < enable.lineno]
    assert persist, "Persist touch_previous before activating the hardware mode"
    spawns = calls(main, "Popen")
    assert len(spawns) == 2 and spawns[0].lineno < read.lineno < enable.lineno < spawns[1].lineno
    finalizers = [n for n in ast.walk(main) if isinstance(n, ast.Try) and n.finalbody]
    assert any(any(calls(n, "restore_mode") for n in block.finalbody)
               for block in finalizers), "Normal cleanup must restore touch mode"
    assert calls(recover, "restore_mode"), "Independent recovery must restore touch mode"
    assert calls(recover, "stop_child")[0].lineno < calls(recover, "restore_mode")[0].lineno
    for name in ("touch_mode.py", "device_input.py"):
        assert (directory / name).is_file(), f"Missing runtime input dependency: {name}"
    app = ast.parse((directory / "app.py").read_text(encoding="utf-8"))
    assert calls(app, "set_focus") and calls(app, "cancel_touch")
    assert calls(app, "diagnostics"), "Keep evidence for input readiness"


def validate_archive(path):
    prefix = "Ports/SlayTheSpireGeometryP1/"
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read(prefix + "manifest.json"))
        assert manifest["game_assets"] is False
        for name in ("touch_mode.py", "device_input.py", "supervisor.py", "app.py"):
            data = archive.read(prefix + name)
            assert data == (P1 / name).read_bytes(), f"Stale packaged {name}"
            assert manifest["files"][name] == hashlib.sha256(data).hexdigest()


def main():
    validate_source()
    archive = ROOT / "dist/SlayTheSpire_P1_Geometry_game-free.zip"
    if archive.exists():
        validate_archive(archive)
    print("Touch lifecycle and package contract passed")


if __name__ == "__main__":
    main()
