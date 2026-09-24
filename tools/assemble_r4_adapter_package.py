"""Build the public R4 dual-screen adapter without game data or player data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prototype.r3.launch_profile import configure


UPSTREAM = ROOT / "upstream" / "slaythespire"
HERE = ROOT / "prototype" / "r3"
PREFIX = "Ports/Slay the Spire for RGDSplus/"
ENTRY = "Ports/Slay the Spire for RGDSplus.sh"
BUILD = "slay-the-spire-for-rgdsplus-adapter-20260924-01"
OUTPUT = ROOT / "dist" / "Slay the Spire for RGDSplus.zip"

ADAPTER_SOURCES = {
    "controller-injector.jar": UPSTREAM / "controller-injector.jar",
    "texcompress-agent.jar": UPSTREAM / "texcompress-agent.jar",
    "libtexcompress.so": UPSTREAM / "libtexcompress.so",
    "libastcenc-neon-shared.so": UPSTREAM / "libastcenc-neon-shared.so",
    "libwrap.so": UPSTREAM / "libwrap.so",
    "libXrandr.so.2": UPSTREAM / "libXrandr.so.2",
    "libgdx-controllers-desktop.so": UPSTREAM / "libgdx-controllers-desktop.so",
    "twitchconfig.txt": UPSTREAM / "twitchconfig.txt",
    "rgds-dual-r3.jar": HERE / "build" / "rgds-dual-r3.jar",
    "librgds-dual.so": HERE / "build" / "librgds-dual.so",
    "rgds-input-agent.jar": ROOT / "platform" / "rgds-input-agent.jar",
    "rgds_exit.py": ROOT / "platform" / "rgds_exit.py",
    "run-java.sh": ROOT / "packaging" / "run-java.sh",
    "runtime_preflight.sh": ROOT / "packaging" / "runtime_preflight.sh",
    "slay.gptk": ROOT / "packaging" / "slay.gptk",
    "rgds-gamecontroller.txt": ROOT / "packaging" / "rgds-gamecontroller.txt",
    "patch_safe.sh": ROOT / "platform" / "patch_safe.sh",
    "tools/xdelta3": ROOT / "platform" / "xdelta3",
    "supervisor.py": HERE / "supervisor.py",
    "touch_bridge.py": HERE / "touch_bridge.py",
    "touch_transport.py": HERE / "touch_transport.py",
    "diagnostic_io.py": HERE / "diagnostic_io.py",
    "touch_mode.py": ROOT / "prototype" / "p1" / "touch_mode.py",
    "device_input.py": ROOT / "prototype" / "p1" / "device_input.py",
    "session_runtime.py": ROOT / "prototype" / "p1" / "supervisor.py",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_name(name: str) -> None:
    parts = PurePosixPath(name).parts
    lower = name.lower()
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or ".." in parts
        or any(
            part.lower()
            in {"saves", "betapreferences", "preferences", "runs", "logs", "__pycache__"}
            for part in parts
        )
        or lower.endswith((".autosave", ".backup", ".log", ".pem", ".key"))
    ):
        raise ValueError("unsafe or player-data archive path: " + name)
    if name.startswith("Ports/") and not (
        name.startswith(PREFIX) or name == ENTRY
    ):
        raise ValueError("archive touches another port: " + name)


def validate_names(names: list[str]) -> None:
    if len(set(names)) != len(names):
        raise ValueError("duplicate archive paths")
    for name in names:
        validate_name(name)
        if Path(name).name.lower() in {
            "desktop-1.0.jar",
            "slaythespire.exe",
            "mod-uploader.jar",
            "mts-launcher.jar",
        }:
            raise ValueError("game payload leaked into adapter archive: " + name)


def entry_bytes() -> bytes:
    source = HERE / "Slay the Spire for RGDSplus.sh"
    data = source.read_bytes()
    if b'"$PORTS/Slay the Spire for RGDSplus/supervisor.py"' not in data:
        raise AssertionError("unexpected R4 entrypoint")
    if b"SlayTheSpireDualR4" in data:
        raise AssertionError("public entry still points at the legacy directory")
    if b"--seconds 0" not in data:
        raise AssertionError("R4 entrypoint must remain menu-launched")
    return data


def generated_game_launcher() -> bytes:
    """The supervisor starts the configured JVM launcher, not another supervisor."""
    return generated_launcher()


def generated_launcher() -> bytes:
    source = (ROOT / "packaging" / "launch.sh").read_text(encoding="utf-8")
    return configure(source).encode()


def generated_manifest(files: dict[str, str]) -> bytes:
    manifest = {
        "build": BUILD,
        "distribution": "public dual-screen adapter-only package",
        "game_assets_in_adapter": False,
        "required_user_file": PREFIX + "desktop-1.0.jar",
        "required_user_file_note": "Copy a legally purchased desktop-1.0.jar here before launch.",
        "logic_viewport": [1024, 768],
        "default_profile": {
            "fps": 30,
            "initial_heap_mb": 32,
            "heap_mb": 128,
            "gc": "Serial",
            "jit_tier": 1,
            "audio": True,
            "touch_policy": "native-lower-pointer",
        },
        "runtime_requirements": [
            "PortMaster gptokeyb and control.txt",
            "Python 3 with evdev-compatible gt9xx-0 access",
            "weston_pkg_0.2.squashfs",
            "zulu17.54.21-ca-jre17.0.13-linux.squashfs",
        ],
        "files": files,
    }
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()


def zip_info(name: str, executable: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2026, 9, 24, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def verify_archive(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        validate_names(names)
        manifest = json.loads(archive.read("PACKAGE_MANIFEST.json"))
        expected = set(manifest["files"]) | {
            "PACKAGE_MANIFEST.json",
            "CHECKSUMS.sha256",
            "README.zh-CN.md",
        }
        assert set(names) == expected
        assert manifest["build"] == BUILD
        assert manifest["game_assets_in_adapter"] is False
        assert manifest["required_user_file"] == PREFIX + "desktop-1.0.jar"
        assert not any(
            Path(name).name.lower() in {"desktop-1.0.jar", "slaythespire.exe"}
            for name in names
        )
        for name, expected_hash in manifest["files"].items():
            assert sha256_bytes(archive.read(name)) == expected_hash, name
        assert archive.read(ENTRY) == entry_bytes()
        assert archive.read(PREFIX + "game-launch.sh") == generated_game_launcher()
        checksums = archive.read("CHECKSUMS.sha256").decode("ascii")
        assert checksums == "".join(
            f"{value}  {name}\n" for name, value in manifest["files"].items()
        )
        assert archive.getinfo(ENTRY).external_attr >> 16 & stat.S_IXUSR
        assert archive.getinfo(PREFIX + "game-launch.sh").external_attr >> 16 & stat.S_IXUSR
        assert archive.getinfo(PREFIX + "patch_safe.sh").external_attr >> 16 & stat.S_IXUSR
        for tool in ("xdelta3", "oggenc", "oggdec"):
            name = PREFIX + "tools/" + tool
            assert archive.read(name)[:4] == b"\x7fELF", name
            assert archive.getinfo(name).external_attr >> 16 & stat.S_IXUSR, name
        return manifest


def build(output: Path = OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    files: dict[str, bytes] = {}
    for name, source in ADAPTER_SOURCES.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        files[PREFIX + name] = source.read_bytes()
    tools = UPSTREAM / "tools"
    for source in sorted(tools.rglob("*")):
        if source.is_file():
            relative = source.relative_to(tools).as_posix()
            files[PREFIX + "tools/" + relative] = source.read_bytes()
    files[PREFIX + "game-launch.sh"] = generated_game_launcher()
    files[PREFIX + "build-manifest.json"] = b""
    files[PREFIX + "NOTICES/PortMaster-SlayTheSpire-README.md"] = (
        ROOT / "upstream" / "README.md"
    ).read_bytes()
    files[PREFIX + "NOTICES/upstream-manifest.json"] = (
        ROOT / "upstream-manifest.json"
    ).read_bytes()
    files[PREFIX + "NOTICES/THIRD_PARTY_NOTICES.md"] = (
        ROOT / "packaging" / "THIRD_PARTY_NOTICES.md"
    ).read_bytes()
    files["README.zh-CN.md"] = (
        ROOT / "packaging" / "R4_ADAPTER_ONLY.zh-CN.md"
    ).read_bytes()
    files[ENTRY] = entry_bytes()

    payload = {
        name: sha256_bytes(data)
        for name, data in files.items()
        if name != "README.zh-CN.md" and name not in {"PACKAGE_MANIFEST.json", "CHECKSUMS.sha256"}
        and name not in {PREFIX + "build-manifest.json"}
    }
    payload[ENTRY] = sha256_bytes(files[ENTRY])
    files[PREFIX + "build-manifest.json"] = generated_manifest(payload)
    payload[PREFIX + "build-manifest.json"] = sha256_bytes(files[PREFIX + "build-manifest.json"])

    # Keep only the payload hashes in the manifest; the external README and entry
    # are release metadata and are still covered by the ZIP itself.
    package_manifest = generated_manifest(payload)
    files["PACKAGE_MANIFEST.json"] = package_manifest
    files["CHECKSUMS.sha256"] = "".join(
        f"{value}  {name}\n" for name, value in payload.items()
    ).encode("ascii")

    validate_names(list(files))
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
    ) as archive:
        for name, data in files.items():
            executable = name.endswith(".sh") or Path(name).name in {"xdelta3", "oggenc", "oggdec"}
            archive.writestr(zip_info(name, executable), data)
    verify_archive(output)
    checksum = sha256(output)
    output.with_suffix(".zip.sha256").write_text(
        checksum + "  " + output.name + "\n", encoding="ascii"
    )
    print(
        json.dumps(
            {
                "archive": str(output.resolve()),
                "sha256": checksum,
                "bytes": output.stat().st_size,
                "files": len(files),
                "game_data_included": False,
                "verified": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
