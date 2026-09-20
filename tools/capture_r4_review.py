"""Collect labeled native UI specimens; no claim of natural-flow acceptance."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/r4-review"
DEVICE = ROOT / "prototype/r3/device.py"


def command(action, *args):
    result = subprocess.run([sys.executable, str(DEVICE), action, "--variant", "review", *args],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=100)
    if result.returncode:
        raise RuntimeError(result.stdout[-1500:] + result.stderr[-1500:])
    return result.stdout


def state():
    return json.JSONDecoder().raw_decode(command("status").lstrip())[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", type=int, required=True)
    parser.add_argument("--prefix", default="r4v5")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "captures.json"
    entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    if args.resume:
        until = time.monotonic() + 150
        while time.monotonic() < until:
            current = state().get("state.xml") or {}
            if current.get("menu.screen") == "MAIN_MENU":
                command("key", "--keys", "a")
                break
            time.sleep(3)
        until = time.monotonic() + 120
        while time.monotonic() < until:
            current = state().get("state.xml") or {}
            if current.get("game.mode") == "GAMEPLAY" and current.get("dungeon.screen") == "NONE":
                time.sleep(6)
                break
            time.sleep(3)
        else:
            raise RuntimeError("No idle cloned battle")
    for number in args.ids:
        if not 1 <= number <= 33:
            raise ValueError(number)
        scene = f"u{number:02}"
        name = f"{args.prefix}-{scene}"
        if (OUT / f"{name}-stacked.png").exists():
            raise FileExistsError(name)
        print("Opening", scene, flush=True)
        try:
            result = command("page", "--scene", scene)
            time.sleep(7 if number != 30 else 20)
            current = state()
            dual = current.get("dual-state.xml") or {}
            if dual.get("reviewScene") != scene:
                raise RuntimeError("Specimen did not settle: " + str(dual))
            expected = {10: "U08", 11: "U08", 24: "U08"}.get(number, scene.upper())
            if dual.get("pageId") != expected:
                raise RuntimeError(f"Wrong native page: expected {expected}, got {dual.get('pageId')}")
            command("shot", "--name", name)
            entries[scene] = dict(image=f"{name}-stacked.png", state=f"{name}-state.json",
                                  source="isolated-native-ui-specimen", result=result,
                                  build=dual.get("build"), page=dual.get("pageId"),
                                  visual_review="pending", physical_verified=False)
            print("Captured", scene, "nativePage=" + str(dual.get("pageId")), flush=True)
        except Exception as error:
            entries[scene] = dict(error=str(error), physical_verified=False, visual_review="missing")
            print("FAILED", scene, str(error), flush=True)
            if "No matching R3" in str(error):
                manifest.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
                raise
        manifest.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
