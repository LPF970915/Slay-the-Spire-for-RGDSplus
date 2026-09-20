"""Fetch the fixed Slay the Spire PortMaster adapter without game data."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
REPO = "PortsMaster/PortMaster-New"
COMMIT = "d4a4130059e2c8e8627bc55b78e3e0fae5b038f8"
REMOTE_ROOT = "ports/slaythespire"


def get_json(url: str):
    request = Request(url, headers={"User-Agent": "SlayTheSpire-RGDSplus"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def get_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "SlayTheSpire-RGDSplus"})
    with urlopen(request, timeout=120) as response:
        return response.read()


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def list_directory(path: str) -> list[dict]:
    url = (
        f"https://api.github.com/repos/{REPO}/contents/{path}"
        f"?ref={COMMIT}"
    )
    return get_json(url)


def allowed(path: str) -> bool:
    # These are developer fixtures, not runtime files.
    return not (
        path.startswith("slaythespire/betaPreferences/")
        or path.startswith("slaythespire/sendToDevs/")
    )


def walk(path: str) -> list[dict]:
    entries = []
    for entry in list_directory(path):
        relative = entry["path"][len(REMOTE_ROOT) + 1 :]
        if entry["type"] == "file" and allowed(relative):
            entries.append(entry)
        elif entry["type"] == "dir" and allowed(relative + "/"):
            entries.extend(walk(entry["path"]))
    return entries


def destination(remote_path: str) -> Path:
    relative = remote_path[len(REMOTE_ROOT) + 1 :]
    return ROOT / "upstream" / relative


def fetch(entry: dict, records: list[dict]) -> None:
    data = get_bytes(entry["download_url"])
    if blob_sha(data) != entry["sha"]:
        raise RuntimeError(f"blob hash mismatch: {entry['path']}")
    target = destination(entry["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    records.append(
        {
            "path": target.relative_to(ROOT).as_posix(),
            "source_repo": REPO,
            "source_path": entry["path"],
            "git_blob": entry["sha"],
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    )
    print(f"fetched {target.relative_to(ROOT)} ({len(data)} bytes)", flush=True)


def main() -> None:
    records: list[dict] = []
    for entry in list_directory(REMOTE_ROOT):
        if entry["type"] == "file":
            fetch(entry, records)
        elif entry["name"] == "slaythespire":
            for child in walk(entry["path"]):
                fetch(child, records)

    manifest = {
        "source_repo": REPO,
        "source_commit": COMMIT,
        "source_root": REMOTE_ROOT,
        "game_data_included": False,
        "excluded_paths": [
            "slaythespire/betaPreferences/",
            "slaythespire/sendToDevs/",
        ],
        "files": records,
    }
    manifest_path = ROOT / "upstream-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
