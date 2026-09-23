"""Build isolated adapter binaries; compile against, but never bundle, the game."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "prototype/r3"
BUILD = HERE / "build"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--game",
        type=Path,
        default=Path(os.environ["STS_GAME_JAR"]) if os.environ.get("STS_GAME_JAR") else None,
        help="path to the user's legally obtained desktop-1.0.jar",
    )
    parser.add_argument(
        "--jdk",
        type=Path,
        default=Path(os.environ["JAVA_HOME"]) if os.environ.get("JAVA_HOME") else None,
        help="JDK home; defaults to JAVA_HOME or java tools on PATH",
    )
    args = parser.parse_args()
    if args.game is None:
        parser.error("--game or STS_GAME_JAR is required; the game is never bundled")
    game = args.game.expanduser().resolve()
    if game.name != "desktop-1.0.jar" or not game.is_file():
        parser.error("--game must point to an existing desktop-1.0.jar")

    if args.jdk:
        java_bin = args.jdk / "bin"
        javac = java_bin / ("javac.exe" if os.name == "nt" else "javac")
        java = java_bin / ("java.exe" if os.name == "nt" else "java")
    else:
        javac = Path(shutil.which("javac") or "")
        java = Path(shutil.which("java") or "")
    if not javac.is_file() or not java.is_file():
        parser.error("JDK tools not found; set JAVA_HOME or pass --jdk")

    BUILD.mkdir(exist_ok=True)
    classes = BUILD / "classes"
    classes.mkdir(exist_ok=True)
    cp = os.pathsep.join(
        (
            str(game),
            str(ROOT / "upstream/slaythespire/controller-injector.jar"),
            str(ROOT / "platform/rgds-input-agent.jar"),
        )
    )
    subprocess.run(
        [str(javac), "--release", "11", "-cp", cp, "-d", str(classes),
         *map(str, (HERE / "java").rglob("*.java"))],
        check=True,
    )
    jar = javac.with_name("jar.exe" if os.name == "nt" else "jar")
    subprocess.run(
        [str(jar), "cfm", str(BUILD / "rgds-dual-r3.jar"),
         str(HERE / "MANIFEST.MF"), "-C", str(classes), "rgds"],
        check=True,
    )
    test_cp = cp + os.pathsep + str(classes)
    subprocess.run(
        [str(javac), "--release", "11", "-cp", test_cp, "-d", str(classes),
         str(HERE / "TransformTest.java"), str(HERE / "UiTransformTest.java"),
         str(HERE / "TouchStateTest.java"), str(HERE / "InputChainTest.java"),
         str(HERE / "DragAimTest.java"), str(HERE / "CardFlightPathTest.java"),
         str(HERE / "HandFocusTest.java"), str(HERE / "MapGestureTest.java"),
         str(HERE / "KeyboardModelTest.java")],
        check=True,
    )

    def java_test(*values):
        subprocess.run([str(java), "-cp", test_cp, *values], check=True)

    java_test("TransformTest", str(game))
    java_test("UiTransformTest")
    java_test("TouchStateTest")
    java_test("DragAimTest")
    java_test("CardFlightPathTest")
    java_test("HandFocusTest")
    java_test("MapGestureTest")
    java_test("KeyboardModelTest")
    java_test("InputChainTest", str(game))

    build_posix = str(BUILD).replace("\\", "/")
    wsl_build = "/mnt/" + build_posix[0].lower() + build_posix[2:]
    wsl_source = wsl_build.rsplit("/build", 1)[0] + "/dual_sdl.c"
    subprocess.run(
        ["wsl", "-e", "aarch64-linux-gnu-gcc", "-shared", "-fPIC", "-O2",
         "-Wall", "-Wextra", "-Werror", "-o",
         wsl_build + "/librgds-dual.so", wsl_source, "-ldl"],
        check=True,
    )
    with zipfile.ZipFile(BUILD / "rgds-dual-r3.jar") as jar_file:
        assert all(n.startswith(("META-INF/", "rgds/")) for n in jar_file.namelist())
    print(json.dumps(
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
         for p in BUILD.iterdir() if p.is_file()},
        indent=2,
    ))


if __name__ == "__main__":
    main()
