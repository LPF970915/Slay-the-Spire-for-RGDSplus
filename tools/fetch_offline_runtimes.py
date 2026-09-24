"""Fetch pinned, unmodified ARM64 PortMaster runtimes for offline packaging."""

from __future__ import annotations

import hashlib
import json
import io
import tarfile
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "upstream" / "offline-runtime"
COMMIT = "00b09f76f36cd3ee310df4ae612cee925404b927"
REPO = "PortsMaster/PortMaster-New"
RUNTIMES = {
    "zulu17.54.21-ca-jre17.0.13-linux.squashfs": (
        "zulu17.54.21-ca-jre17.0.13-linux.aarch64.squashfs",
        "bf1dcf91036dfddbbf705e1fdbe31bea70fd7312",
        46895104,
    ),
    "weston_pkg_0.2.squashfs": (
        "weston_pkg_0.2.aarch64.squashfs",
        "92f9b3cd37dcb9bb43c37c0a4eee12d7d0b92e91",
        55398400,
    ),
}
LIBRARIES = {
    "libjpeg.so.8": {
        "package": "pool/main/libj/libjpeg-turbo/libjpeg-turbo8_2.1.2-0ubuntu1_arm64.deb",
        "package_sha256": "1c47447261097e6a2105f4ae6f0bf2c7b1e8c6b8209c8ea40286c69c20f43818",
        "member": "./usr/lib/aarch64-linux-gnu/libjpeg.so.8.2.2",
        "copyright": "./usr/share/doc/libjpeg-turbo8/copyright",
    },
    "libXtst.so.6": {
        "package": "pool/main/libx/libxtst/libxtst6_1.2.3-1build4_arm64.deb",
        "package_sha256": "fd3080718162016acff8e1fba5e9598a6277524bb096da79fae953ced6b97f24",
        "member": "./usr/lib/aarch64-linux-gnu/libXtst.so.6.1.0",
        "copyright": "./usr/share/doc/libxtst6/copyright",
    },
}


def deb_data(data: bytes) -> bytes:
    """Read the data member of an ar archive without extracting arbitrary paths."""
    if data[:8] != b"!<arch>\n":
        raise ValueError("Not a Debian ar archive")
    offset = 8
    while offset + 60 <= len(data):
        header = data[offset:offset + 60]
        if header[58:60] != b"`\n":
            raise ValueError("Invalid ar header")
        name = header[:16].decode("ascii").strip().rstrip("/")
        size = int(header[48:58])
        offset += 60
        member = data[offset:offset + size]
        if len(member) != size:
            raise ValueError("Truncated ar member")
        if name.startswith("data.tar"):
            return member
        offset += size + (size % 2)
    raise ValueError("Debian data.tar missing")


def library_payload(name: str) -> tuple[bytes, bytes]:
    spec = LIBRARIES[name]
    data = (DESTINATION / Path(spec["package"]).name).read_bytes()
    if hashlib.sha256(data).hexdigest() != spec["package_sha256"]:
        raise ValueError("Ubuntu package checksum mismatch: " + name)
    content = deb_data(data)
    if content.startswith(b"\x28\xb5\x2f\xfd"):
        import zstandard
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(content)) as stream:
            content = stream.read()
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
        binary = archive.extractfile(spec["member"]).read()
        copyright_text = archive.extractfile(spec["copyright"]).read()
    if binary[:4] != b"\x7fELF" or binary[18:20] != b"\xb7\0":
        raise ValueError("Expected an ARM64 ELF library")
    return binary, copyright_text


def validate(data: bytes, blob: str, size: int) -> None:
    digest = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if len(data) != size or digest != blob or data[:4] != b"hsqs":
        raise ValueError("Runtime size, Git blob or SquashFS signature mismatch")


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    records = []
    for name, (remote, blob, size) in RUNTIMES.items():
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/runtimes/{remote}"
        target = DESTINATION / name
        if target.exists():
            data = target.read_bytes()
            validate(data, blob, size)
        else:
            print(f"Downloading {remote}", flush=True)
            request = Request(url, headers={"User-Agent": "SlayTheSpire-RGDSplus"})
            with urlopen(request, timeout=180) as response:
                data = response.read()
            validate(data, blob, size)
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(data)
            temporary.replace(target)
        records.append({
            "name": name, "source_url": url, "git_blob": blob,
            "bytes": size, "sha256": hashlib.sha256(data).hexdigest(),
        })
        print(f"Verified {name}", flush=True)
    for name, spec in LIBRARIES.items():
        url = "https://ports.ubuntu.com/ubuntu-ports/" + spec["package"]
        target = DESTINATION / Path(spec["package"]).name
        if not target.exists():
            with urlopen(Request(url, headers={"User-Agent": "SlayTheSpire-RGDSplus"}),
                         timeout=90) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != spec["package_sha256"]:
                raise ValueError("Downloaded Debian package checksum mismatch")
            target.write_bytes(data)
        binary, notice = library_payload(name)
        records.append({"name": "libs/" + name, "source_url": url,
                        "package_sha256": spec["package_sha256"],
                        "sha256": hashlib.sha256(binary).hexdigest(),
                        "bytes": len(binary)})
        print(f"Verified {name} with upstream copyright notice", flush=True)
    (DESTINATION / "manifest.json").write_text(
        json.dumps({"source_repo": REPO, "source_commit": COMMIT,
                    "architecture": "aarch64", "files": records}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
