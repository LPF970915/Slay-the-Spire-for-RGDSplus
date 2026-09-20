"""Proven evdev capture for the native UI milestone; never submits game actions."""

import json
from pathlib import Path
import signal
import time

from device_input import Devices

ROOT = Path(__file__).resolve().parent


def heartbeat_focused(text, now):
    try:
        flag, timestamp = text.split()
        age = now - float(timestamp)
        return flag == "1" and 0 <= age < 1.5
    except (ValueError, TypeError):
        return False


def main():
    requested = False
    def stop(*_):
        nonlocal requested
        requested = True
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    trace = (ROOT / "logs" / f"touch-{time.time_ns()}.jsonl").open("w", buffering=1)
    def emit(event):
        trace.write(json.dumps(dict(t=time.monotonic(), policy="capture-only", **event)) + "\n")
    devices = Devices(emit=emit)
    focused = False
    next_report = 0
    try:
        while not requested:
            heartbeat = ROOT / "logs/window-focus.txt"
            try:
                # Card-2 timestamps can have two-second granularity.
                active = heartbeat_focused(heartbeat.read_text(), time.monotonic())
            except OSError:
                active = False
            if focused != active:
                focused = active
                devices.cancel_touch()
                devices.set_focus(focused)
                emit(dict(event="focus", focused=focused))
            for action in devices.poll(time.monotonic()):
                if action[0] in ("down", "move", "up", "cancel"):
                    emit(dict(event="touch", action=action))
            if time.monotonic() >= next_report:
                state = dict(policy="capture-only", physical_verified=False, **devices.diagnostics())
                temp = ROOT / "logs/touch-state.tmp"
                temp.write_text(json.dumps(state))
                temp.replace(ROOT / "logs/touch-state.json")
                next_report = time.monotonic() + 1
            time.sleep(.008)
    finally:
        devices.cancel_touch()
        devices.close()
        trace.close()


if __name__ == "__main__":
    main()
