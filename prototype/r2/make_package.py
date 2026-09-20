"""R2 packages proven R1 helpers byte-for-byte; never edits the R1 installation."""

import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "prototype/r2"
P1 = ROOT / "prototype/p1"
BUILD = "r2-touch-probe-20260920-2"
ENTRY = "Slay the Spire R2 Touch Probe.sh"
PREFIX = "Ports/SlayTheSpireTouchR2/"


def files():
    result = {name: HERE / name for name in ("app.py", "probe.py", "supervisor.py", "README.zh-CN.md")}
    result.update({name: P1 / name for name in
                   ("launch.sh", "device_input.py", "touch_mode.py", "geometry.py")})
    result["p1_display.py"] = P1 / "app.py"
    result["session_runtime.py"] = P1 / "supervisor.py"
    return result


def main():
    sys.path.insert(0, str(ROOT / "tools"))
    from test_touch_contract import validate_source
    validate_source()
    output = ROOT / "dist/SlayTheSpire_R2_TouchProbe_game-free.zip"
    output.parent.mkdir(exist_ok=True)
    checksums = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files().items()}
    manifest = dict(build=BUILD, files=checksums, game_assets=False,
                    inherited_from="p1-geometry-20260920-aim3")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in files().items():
            archive.writestr(PREFIX + name, path.read_bytes())
        archive.writestr(PREFIX + "manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("Ports/" + ENTRY, (HERE / ENTRY).read_bytes())
    with zipfile.ZipFile(output) as archive:
        assert len(archive.namelist()) == len(checksums) + 2
        assert all(name.startswith(PREFIX) or name == "Ports/" + ENTRY for name in archive.namelist())
        for name, path in files().items():
            assert archive.read(PREFIX + name) == path.read_bytes()
    print(output)
    print("sha256", hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
