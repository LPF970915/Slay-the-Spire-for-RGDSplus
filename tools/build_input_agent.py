"""Compile only adapter code, using upstream's existing Javassist dependency."""

import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    javac = shutil.which("javac")
    if not javac:
        raise SystemExit("A JDK with javac is required")
    java_home = Path(os.environ.get("JAVA_HOME", Path(javac).resolve().parents[1]))
    jar = java_home / "bin" / ("jar.exe" if os.name == "nt" else "jar")
    if not jar.exists():
        jar = shutil.which("jar")
    if not jar:
        raise SystemExit("JDK jar tool not found; set JAVA_HOME")
    output = ROOT / "cache/input-classes"
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([javac, "--release", "11", "-cp",
                    str(ROOT / "upstream/slaythespire/controller-injector.jar"),
                    "-d", str(output),
                    *map(str, sorted((ROOT / "platform/java/rgds").glob("*.java")))], check=True)
    subprocess.run([str(jar), "cfm", str(ROOT / "platform/rgds-input-agent.jar"),
                    str(ROOT / "platform/java/MANIFEST.MF"),
                    "-C", str(output), "rgds"], check=True)


if __name__ == "__main__":
    main()
