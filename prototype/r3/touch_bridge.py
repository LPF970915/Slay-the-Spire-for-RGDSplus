"""Proven evdev lifecycle with opt-in, ordered native lower-screen pointer input."""

import json
import os
from pathlib import Path
import signal
import time

from device_input import Devices
from touch_transport import TouchTransport

ROOT = Path(__file__).resolve().parent


def heartbeat_focused(text, now):
    try:
        flag, timestamp = text.split()
        age = now - float(timestamp)
        return flag == "1" and 0 <= age < 1.5
    except (ValueError, TypeError):
        return False


def main():
    directory = Path(os.environ.get("RGDS_DIAGNOSTICS_DIR", str(ROOT / "logs")))
    live = os.environ.get("RGDS_R4_TOUCH_LIVE") == "1"
    policy = "native-lower-pointer" if live else "capture-only"
    transport = TouchTransport(directory) if live else None
    requested = False
    def stop(*_):
        nonlocal requested
        requested = True
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    trace = (directory / f"touch-{time.time_ns()}.jsonl").open("w", buffering=1)
    def emit(event):
        trace.write(json.dumps(dict(t=time.monotonic(), policy=policy, **event)) + "\n")
    devices = Devices(emit=emit)
    focused = False
    next_report = 0
    try:
        while not requested:
            heartbeat = directory / "window-focus.txt"
            try:
                # Card-2 timestamps can have two-second granularity.
                active = heartbeat_focused(heartbeat.read_text(), time.monotonic())
            except OSError:
                active = False
            if focused != active:
                focused = active
                devices.cancel_touch()
                devices.set_focus(focused)
                if transport:
                    transport.cancel()
                emit(dict(event="focus", focused=focused))
            actions = devices.poll(time.monotonic())
            if transport:
                transport.tick()
                transport.actions(actions, focused)
            for action in actions:
                if action[0] in ("down", "move", "up", "cancel"):
                    emit(dict(event="touch", action=action))
            if time.monotonic() >= next_report:
                state = dict(policy=policy, physical_verified=False,
                             connected=bool(transport and transport.socket),
                             sent=transport.sent if transport else 0, **devices.diagnostics())
                temp = directory / "touch-state.tmp"
                temp.write_text(json.dumps(state))
                temp.replace(directory / "touch-state.json")
                next_report = time.monotonic() + 1
            time.sleep(.008)
    finally:
        devices.cancel_touch()
        if transport:
            transport.cancel()
            transport.close()
        devices.close()
        trace.close()


if __name__ == "__main__":
    main()
