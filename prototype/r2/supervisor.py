"""R2 lifecycle uses the proven mode/input helpers; both probes are exclusive."""

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
from session_runtime import identity, send, stop_child
from touch_mode import read_mode, enable_mode, restore_mode

ROOT = Path(__file__).resolve().parent
PEER = ROOT.parent / "SlayTheSpireGeometryP1"


def recover(path):
    state = json.loads(path.read_text())
    while identity(state["owner"]) == state["birth"]:
        time.sleep(.25)
    state = json.loads(path.read_text())
    if state["child"]:
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
    paths = [ROOT / "logs/session.lock"]
    if (PEER / "logs").is_dir():
        paths.append(PEER / "logs/session.lock")
    locks = []
    try:
        for path in paths:
            lock = path.open("a+")
            locks.append(lock)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("R1 or R2 is already running", flush=True)
        return
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text().strip() in ("java", "love", "love.aarch64", "retroarch"):
                raise RuntimeError("Close other games before R2")
            parts = (comm.parent / "cmdline").read_bytes().split(b"\0")
            if any(str(root / "app.py").encode() in parts for root in (ROOT, PEER)):
                raise RuntimeError("A probe renderer is still active")
        except FileNotFoundError:
            pass
    menus = []
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            if comm.read_text().strip() == "dmenu.bin":
                pid = int(comm.parent.name)
                status = (comm.parent / "stat").read_text().rsplit(")", 1)[1].split()[0]
                if status not in ("T", "t"):
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
    child = guardian = None
    inputs = Devices(guard=True)
    requested = False
    def request_exit(*_):
        nonlocal requested
        requested = True
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, request_exit)
    state_path = ROOT / f"logs/recovery-{os.getpid()}.json"
    state = dict(owner=os.getpid(), birth=identity(os.getpid()), menus=menus,
                 child=None, touch_previous=None)
    # Keep both locks alive in the renderer and guardian after supervisor death.
    inherited_locks = tuple(lock.fileno() for lock in locks)
    try:
        state_path.write_text(json.dumps(state))
        guardian = subprocess.Popen([sys.executable, str(ROOT / "supervisor.py"),
                                     "--recover", str(state_path)], stdout=log, stderr=log,
                                    start_new_session=True, pass_fds=inherited_locks)
        for pid, birth in menus:
            send(pid, birth, signal.SIGSTOP)
        state["touch_previous"] = read_mode(log=touch_log)
        temporary = ROOT / "logs/recovery.tmp"
        temporary.write_text(json.dumps(state))
        temporary.replace(state_path)
        if not enable_mode(state["touch_previous"], log=touch_log):
            raise RuntimeError("R2 requires verified touch-mode activation")
        child = subprocess.Popen([sys.executable, str(ROOT / "app.py"), *app_args],
                                 env=env, cwd=ROOT, stdout=log, stderr=log,
                                 start_new_session=True, pass_fds=inherited_locks)
        child_birth = identity(child.pid)
        state["child"] = [child.pid, child_birth]
        temporary.write_text(json.dumps(state))
        temporary.replace(state_path)
        (ROOT / "logs/session.json").write_text(json.dumps(state))
        while child.poll() is None and not requested:
            now = time.monotonic()
            inputs.poll(now)
            requested = inputs.exit_held(now)
            time.sleep(.02)
        if child.poll() is None:
            touch_log("[supervisor] independent exit requested")
            stop_child(child.pid, child_birth)
        rc = child.wait()
        touch_log(f"[supervisor] app_exit={rc}")
        if rc and not requested:
            raise RuntimeError(f"R2 failed rc={rc}; see logs/latest.log")
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
        for lock in locks:
            lock.close()


if __name__ == "__main__":
    main()
