"""Build isolated adapter binaries; compile against, but never bundle, the game."""

import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "prototype/r3"
GAME = Path("D:/Program Files/Steam/steamapps/common/SlayTheSpire/desktop-1.0.jar")
JDK = Path("C:/Program Files/Java/jdk-25/bin")
BUILD = HERE / "build"


def main():
    BUILD.mkdir(exist_ok=True)
    classes = BUILD / "classes"
    classes.mkdir(exist_ok=True)
    cp = str(GAME) + ";" + str(ROOT / "upstream/slaythespire/controller-injector.jar")
    subprocess.run([str(JDK / "javac.exe"), "--release", "11", "-cp", cp, "-d", str(classes),
                    *map(str, (HERE / "java").rglob("*.java"))], check=True)
    subprocess.run([str(JDK / "jar.exe"), "cfm", str(BUILD / "rgds-dual-r3.jar"),
                    str(HERE / "MANIFEST.MF"), "-C", str(classes), "rgds"], check=True)
    test_cp = cp + ";" + str(classes)
    subprocess.run([str(JDK / "javac.exe"), "--release", "11", "-cp", test_cp,
                    "-d", str(classes), str(HERE / "TransformTest.java"),
                    str(HERE / "UiTransformTest.java")], check=True)
    subprocess.run([str(JDK / "java.exe"), "-cp", test_cp, "TransformTest", str(GAME)], check=True)
    subprocess.run([str(JDK / "java.exe"), "-cp", test_cp, "UiTransformTest"], check=True)
    subprocess.run(["wsl", "-e", "aarch64-linux-gnu-gcc", "-shared", "-fPIC", "-O2",
                    "-Wall", "-Wextra", "-Werror", "-o",
                    "/mnt/d/Works/Slay the Spire for RGDSplus/prototype/r3/build/librgds-dual.so",
                    "/mnt/d/Works/Slay the Spire for RGDSplus/prototype/r3/dual_sdl.c", "-ldl"], check=True)
    with zipfile.ZipFile(BUILD / "rgds-dual-r3.jar") as jar:
        assert all(n.startswith(("META-INF/", "rgds/")) for n in jar.namelist())
    print(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in BUILD.iterdir() if p.is_file()}, indent=2))


if __name__ == "__main__":
    main()
