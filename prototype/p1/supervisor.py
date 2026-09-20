"""Single-instance, silent P1 launcher; exit input is independent of rendering."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from device_input import Devices
from touch_mode import read_mode, enable_mode, restore_mode

ROOT = Path(__file__).resolve().parent


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19] if fields[0] != "Z" else None
    except (OSError, IndexError):
        return None


def send(pid, birth, sig):
    if birth is not None and identity(pid) == birth:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass


def stop_child(pid, birth):
    send(pid, birth, signal.SIGTERM)
    deadline = time.monotonic() + 3
    while identity(pid) == birth and time.monotonic() < deadline:
        time.sleep(0.05)
    send(pid, birth, signal.SIGKILL)


def recover(path):
    state = json.loads(path.read_text())
    while identity(state["owner"]) == state["birth"]:
        time.sleep(0.25)
    state = json.loads(path.read_text())
    if state.get("child"):
        stop_child(*state["child"])
    restore_mode(state.get("touch_previous"))
    for pid, birth in state["menus"]:
        send(pid, birth, signal.SIGCONT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recover", type=Path)
    args, app_args = parser.parse_known_args()
    if args.recover:
        recover(args.recover)
        return
    (ROOT / "logs").mkdir(exist_ok=True)
    lock = (ROOT / "logs/session.lock").open("a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("P1 already running", flush=True)
        return
    # Never start alongside the real game or another game runtime.
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text().strip() in ("java", "love", "love.aarch64", "retroarch"):
                raise RuntimeError("Another game is running; close it before starting P1")
            parts = (comm.parent / "cmdline").read_bytes().split(b"\0")
            if str(ROOT / "app.py").encode() in parts:
                raise RuntimeError("Previous P1 renderer is still exiting; retry shortly")
        except FileNotFoundError:
            pass
    menus = []
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text().strip() == "dmenu.bin":
                pid = int(comm.parent.name)
                state = (comm.parent / "stat").read_text().rsplit(")", 1)[1].split()[0]
                if state not in ("T", "t"):
                    menus.append((pid, identity(pid)))
        except FileNotFoundError:
            pass
    env = os.environ.copy()
    env.update(XDG_RUNTIME_DIR="/var/run", WAYLAND_DISPLAY="wayland-0",
               SDL_VIDEODRIVER="wayland", PYTHONUNBUFFERED="1")
    for key in ("LD_PRELOAD", "WRAPPED_PRELOAD"):
        env.pop(key, None)
    log = (ROOT / "logs/latest.log").open("w", buffering=1)
    def touch_log(message):
        print(message, file=log, flush=True)
    child = None
    guardian = None
    inputs = Devices(guard=True)
    requested = False

    def exit_requested(*_):
        nonlocal requested
        requested = True

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, exit_requested)
    state_path = ROOT / f"logs/recovery-{os.getpid()}.json"
    state = dict(owner=os.getpid(), birth=identity(os.getpid()), menus=menus, child=None,
                 touch_previous=None)
    try:
        # Guardian starts before menu STOP and remains independent of rendering.
        state_path.write_text(json.dumps(state))
        guardian = subprocess.Popen([sys.executable, str(ROOT / "supervisor.py"),
                                     "--recover", str(state_path)],
                                    stdout=log, stderr=log, start_new_session=True)
        for pid, birth in menus:
            send(pid, birth, signal.SIGSTOP)
        state["touch_previous"] = read_mode(log=touch_log)
        temporary = ROOT / "logs/recovery.tmp"
        temporary.write_text(json.dumps(state))
        temporary.replace(state_path)
        enable_mode(state["touch_previous"], log=touch_log)
        child = subprocess.Popen([sys.executable, str(ROOT / "app.py"), *app_args],
                                 env=env, cwd=ROOT, stdout=log, stderr=log,
                                 start_new_session=True)
        child_birth = identity(child.pid)
        state["child"] = [child.pid, child_birth]
        # Guardian reloads the child identity after owner death.
        temporary = ROOT / "logs/recovery.tmp"
        temporary.write_text(json.dumps(state))
        temporary.replace(state_path)
        (ROOT / "logs/session.json").write_text(json.dumps(state))
        while child.poll() is None and not requested:
            now = time.monotonic()
            inputs.poll(now)
            requested = inputs.exit_held(now)
            time.sleep(0.02)
        if child.poll() is None:
            print("[supervisor] independent exit requested", file=log)
            stop_child(child.pid, child_birth)
        result = child.wait()
        print(f"[supervisor] app_exit={result}", file=log)
        if result and not requested:
            raise RuntimeError(f"P1 failed, see {ROOT / 'logs/latest.log'}")
    finally:
        if child and child.poll() is None:
            stop_child(child.pid, identity(child.pid))
            child.wait()
        inputs.close()
        restore_mode(state.get("touch_previous"), log=touch_log)
        for pid, birth in menus:
            send(pid, birth, signal.SIGCONT)
        if guardian:
            guardian.terminate()
            guardian.wait()
        log.close()
        lock.close()


if __name__ == "__main__":
    main()
