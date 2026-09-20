"""Inspect the staged snapshot before uploading this private adapter baseline."""

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_JARS = {
    "platform/rgds-input-agent.jar",
    "prototype/r3/build/rgds-dual-r3.jar",
}
BINARY_PATHS = ADAPTER_JARS | {
    "platform/librgds-sdl.so",
    "platform/xdelta3",
    "prototype/r3/build/librgds-dual.so",
}
BLOCKED = {
    "cache", "private", "saves", "validation", "upstream", "dist",
    "__pycache__", "betaPreferences", "sendToDevs", "logs",
}


def main():
    listing = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=ROOT)
    assert listing, "Stage the intended baseline first"
    entries = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", 1)
        mode, oid, stage = header.split()
        name = raw_path.decode("utf-8")
        path = PurePosixPath(name)
        assert mode in (b"100644", b"100755") and stage == b"0", name
        assert not BLOCKED.intersection(path.parts), name
        assert not path.name.startswith(".env"), name
        assert path.suffix.lower() not in (
            ".png", ".jpg", ".jpeg", ".pam", ".ppm", ".zip", ".exe",
            ".love", ".squashfs", ".log", ".pyc", ".class", ".pem", ".key",
        ), name
        data = subprocess.check_output(["git", "cat-file", "blob", oid.decode()], cwd=ROOT)
        assert len(data) < 10_000_000, name
        if name in ADAPTER_JARS:
            with zipfile.ZipFile(io.BytesIO(data)) as jar:
                assert all(n.startswith(("META-INF/", "rgds/")) for n in jar.namelist()), name
        elif name in BINARY_PATHS:
            assert data.startswith(b"\x7fELF"), name
        else:
            assert path.suffix.lower() not in (".jar", ".so", ".dll"), name
            text = data.decode("utf-8")
            assert "\0" not in text, name
            for pattern in (
                r"gh[pousr]_[A-Za-z0-9]{20,}",
                r"github_pat_[A-Za-z0-9_]{20,}",
                r"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
                r"""(?i)password\s*=\s*['"](?!\.\.\.['"])[^'"]+['"]""",
            ):
                assert not re.search(pattern, text), "Possible credential in " + name
        entries.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    destination = ROOT / "validation/baseline-git-payload.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"PASS: {len(entries)} staged files, {sum(e['bytes'] for e in entries)} bytes")
    print("Adapter-only JAR contents, no game files/private evidence/credential literals")
    print(destination)


if __name__ == "__main__":
    main()
