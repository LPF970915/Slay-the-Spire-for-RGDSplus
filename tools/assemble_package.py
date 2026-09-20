"""Assemble a game-free RGDSplus package."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream"
OUT = ROOT / "dist" / "Ports"
APP = OUT / "SlayTheSpire"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_required() -> None:
    if not (UPSTREAM / "slaythespire").is_dir():
        raise SystemExit("run tools/fetch_upstream.py first")
    if OUT.exists():
        shutil.rmtree(OUT)
    APP.mkdir(parents=True)
    for name in (
        "controller-injector.jar",
        "FontSizeAgent.jar",
        "libXrandr.so.2",
        "libastcenc-neon-shared.so",
        "libgdx-controllers-desktop.so",
        "libtexcompress.so",
        "libwrap.so",
        "texcompress-agent.jar",
        "twitchconfig.txt",
    ):
        shutil.copy2(UPSTREAM / "slaythespire" / name, APP / name)
    shutil.copytree(UPSTREAM / "slaythespire" / "tools", APP / "tools")
    shutil.copy2(ROOT / "platform" / "xdelta3", APP / "tools" / "xdelta3")
    (APP / "tools" / "xdelta3").chmod(0o755)
    for name in ("README.md", "gameinfo.xml", "port.json", "screenshot.png"):
        shutil.copy2(UPSTREAM / name, APP / name)
    shutil.copy2(ROOT / "packaging" / "launch.sh", APP / "launch.sh")
    shutil.copy2(ROOT / "packaging" / "run-java.sh", APP / "run-java.sh")
    shutil.copy2(ROOT / "packaging" / "slay.gptk", APP / "slay.gptk")
    shutil.copy2(ROOT / "packaging" / "info.displayconfig", APP / "info.displayconfig")
    shutil.copy2(ROOT / "packaging" / "rgds-gamecontroller.txt", APP / "rgds-gamecontroller.txt")
    shutil.copy2(ROOT / "platform" / "rgds_exit.py", APP / "rgds_exit.py")
    shutil.copy2(ROOT / "platform" / "rgds-input-agent.jar", APP / "rgds-input-agent.jar")
    shutil.copy2(ROOT / "platform" / "librgds-sdl.so", APP / "librgds-sdl.so")
    shutil.copy2(ROOT / "platform" / "patch_safe.sh", APP / "patch_safe.sh")
    shutil.copy2(
        ROOT / "packaging" / "README.zh-CN.md",
        APP / "README.zh-CN.md",
    )
    shutil.copy2(
        ROOT / "packaging" / "THIRD_PARTY_NOTICES.md",
        APP / "THIRD_PARTY_NOTICES.md",
    )
    entrypoint = OUT / "Slay the Spire for RGDSplus.sh"
    shutil.copy2(ROOT / "packaging" / "Slay the Spire for RGDSplus.sh", entrypoint)
    for path in (entrypoint, APP / "launch.sh", APP / "patch_safe.sh"):
        path.chmod(0o755)


def main() -> None:
    copy_required()
    manifest = {
        "build": "rgdsplus-slaythespire-p0-single-20260920-input3",
        "entrypoint": "Ports/Slay the Spire for RGDSplus.sh",
        "game_data_included": False,
        "required_user_file": "Ports/SlayTheSpire/desktop-1.0.jar",
        "logic_viewport": [1024, 768],
        "window_mode": "system-wayland SDL window with auxiliary XWayland",
        "patch_revision": "p0-single-3",
        "input_revision": "rgds-balatro-mapping-3-edges-piles",
        "render_revision": "native-4x3-astc-rgba3-smallraw",
        "portmaster_commit": json.loads(
            (ROOT / "upstream-manifest.json").read_text(encoding="utf-8")
        )["source_commit"],
        "runtime_requirements": [
            "weston_pkg_0.2.squashfs",
            "zulu17.54.21-ca-jre17.0.13-linux.squashfs",
        ],
        "distribution": "game-free adapter; user supplies purchased JAR",
    }
    (APP / "build-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    files = sorted(
        p for p in OUT.rglob("*") if p.is_file() and p.name != "CHECKSUMS.sha256"
    )
    (APP / "CHECKSUMS.sha256").write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(APP).as_posix()}\n"
            for path in files
            if path.is_relative_to(APP) and path.name not in {
                "CHECKSUMS.sha256", "info.displayconfig"
            }
        )
        + f"{sha256(OUT / 'Slay the Spire for RGDSplus.sh')}  "
        "../Slay the Spire for RGDSplus.sh\n",
        encoding="utf-8",
    )
    package_files = sorted(path for path in OUT.rglob("*") if path.is_file())
    package = ROOT / "dist" / "SlayTheSpire_RGDSplus_P0_game-free.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path in package_files:
            relative = path.relative_to(OUT).as_posix()
            info = zipfile.ZipInfo.from_file(path, "Ports/" + relative)
            info.create_system = 3
            if path.name.endswith(".sh"):
                info.external_attr = 0o100755 << 16
            else:
                info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if any(name.endswith(("desktop-1.0.jar", ".exe")) for name in names):
            raise AssertionError("game data leaked into package")
    print(package)


if __name__ == "__main__":
    main()
