"""Assemble only the standalone game-free P1 prototype, never the game port."""

import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ("geometry.py", "device_input.py", "app.py", "supervisor.py", "launch.sh",
         "touch_mode.py", "README.zh-CN.md")


def main():
    output = ROOT.parents[1] / "dist/SlayTheSpire_P1_Geometry_game-free.zip"
    output.parent.mkdir(exist_ok=True)
    prefix = "Ports/SlayTheSpireGeometryP1/"
    checksums = {}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            data = (ROOT / name).read_bytes()
            checksums[name] = hashlib.sha256(data).hexdigest()
            archive.writestr(prefix + name, data)
        entry = "Slay the Spire P1 Geometry.sh"
        archive.writestr("Ports/" + entry, (ROOT / entry).read_bytes())
        archive.writestr(prefix + "manifest.json", json.dumps(
            dict(build="p1-geometry-20260920-aim3", files=checksums, game_assets=False), indent=2))
    with zipfile.ZipFile(output) as archive:
        assert len(archive.namelist()) == len(FILES) + 2
        assert all(name.startswith(prefix) or name == "Ports/" + entry
                   for name in archive.namelist())
        assert not any(name.endswith((".jar", ".love", ".exe")) for name in archive.namelist())
    import sys
    sys.path.insert(0, str(ROOT.parents[1] / "tools"))
    from test_touch_contract import validate_archive, validate_source
    validate_source()
    validate_archive(output)
    print(output)
    print("sha256", hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
