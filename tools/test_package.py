"""Static package checks that do not require a device or game data."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    allowed_adapter_jars = {
        "controller-injector.jar",
        "texcompress-agent.jar",
        "FontSizeAgent.jar",
        "rgds-input-agent.jar",
    }
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".jar", ".exe", ".love"}:
            if path == ROOT / "prototype/r3/build/rgds-dual-r3.jar":
                with zipfile.ZipFile(path) as adapter:
                    assert all(n.startswith(("META-INF/", "rgds/"))
                               for n in adapter.namelist())
                continue
            if "upstream" not in path.parts and path.name not in allowed_adapter_jars:
                raise AssertionError(f"unexpected game-like file: {path}")
    patcher = (ROOT / "platform" / "patch_safe.sh").read_text(encoding="utf-8")
    assert "rm \"$INPUT_ZIP\"" not in patcher
    assert "desktop-1.0.jar" in patcher
    assert (ROOT / "platform" / "xdelta3").read_bytes()[:4] == b"\x7fELF"
    assert "tools/xdelta3" in patcher
    assert "/mnt/mmc/Ports" in (
        ROOT / "packaging" / "launch.sh"
    ).read_text(encoding="utf-8")
    if (ROOT / "dist" / "SlayTheSpire_RGDSplus_P0_game-free.zip").exists():
        with zipfile.ZipFile(
            ROOT / "dist" / "SlayTheSpire_RGDSplus_P0_game-free.zip"
        ) as archive:
            assert all(
                not name.lower().endswith((".jar", ".exe", ".love"))
                or Path(name).name in allowed_adapter_jars
                for name in archive.namelist()
            )
            assert "Ports/SlayTheSpire/run-java.sh" in archive.namelist()
            assert archive.read("Ports/SlayTheSpire/info.displayconfig").decode().splitlines() == [
                "1024", "768", "24", "false", "true", "false"
            ]
            # This file is rewritten by the launcher and game, unlike adapter binaries.
            checksums = archive.read("Ports/SlayTheSpire/CHECKSUMS.sha256").decode()
            assert "info.displayconfig" not in checksums
            assert "rgds-input-agent.jar" in checksums
            assert "SOURCE_COPY" not in patcher
            assert 'unzip -q "$INPUT_ZIP"' in patcher
            for name in ("launch.sh", "run-java.sh", "patch_safe.sh",
                         "rgds_exit.py", "rgds-gamecontroller.txt", "slay.gptk",
                         "rgds-input-agent.jar", "librgds-sdl.so"):
                source = ROOT / ("platform" if name in {
                    "patch_safe.sh", "rgds_exit.py", "rgds-input-agent.jar", "librgds-sdl.so"
                } else "packaging") / name
                assert archive.read(f"Ports/SlayTheSpire/{name}") == source.read_bytes()
            with zipfile.ZipFile(ROOT / "platform/rgds-input-agent.jar") as agent:
                assert all(n.startswith(("rgds/", "META-INF/")) for n in agent.namelist())
    mapping = (ROOT / "packaging/rgds-gamecontroller.txt").read_text()
    for binding in ("a:b0", "b:b1", "x:b3", "y:b2", "back:b6",
                    "lefttrigger:b10", "righttrigger:b11", "dpup:h0.1"):
        assert binding in mapping
    from test_touch_contract import validate_source, validate_archive
    validate_source()
    prototype_archive = ROOT / "dist/SlayTheSpire_P1_Geometry_game-free.zip"
    if prototype_archive.exists():
        validate_archive(prototype_archive)
    print("static package checks passed")


if __name__ == "__main__":
    main()
