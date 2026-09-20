"""Own only the isolated R3 process tree; preserve proven touch recovery."""

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
from session_runtime import identity, send, stop_child
from rgds_exit import game_identity, terminate

ROOT = Path(__file__).resolve().parent


def stop_runtime(state):
    log_path = ROOT / "logs/latest-path.txt"
    if log_path.exists():
        log = Path(log_path.read_text().strip())
        if log.parent == ROOT / "logs" and log.suffix == ".log":
            game = game_identity(Path(str(log)[:-4]))
            if game:
                terminate(game)
    if state.get("bridge"):
        stop_child(*state["bridge"])
    if state.get("child"):
        pid, birth = state["child"]
        send(pid, birth, signal.SIGTERM)
        until = time.monotonic() + 12
        while identity(pid) == birth and time.monotonic() < until:
            time.sleep(.1)
        send(pid, birth, signal.SIGKILL)
        # PortMaster may leave its input helper alive after the shell exits.
        # Only this launcher's process group/session is eligible for cleanup.
        for stat in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = stat.read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == pid and int(fields[3]) == pid:
                    owned_pid = int(stat.parent.name)
                    send(owned_pid, fields[19], signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass


def recover(path):
    state = json.loads(path.read_text())
    while identity(state["owner"]) == state["birth"]:
        time.sleep(.25)
    state = json.loads(path.read_text())
    stop_runtime(state)
    restore_mode(state.get("touch_previous"))
    for pid, birth in state["menus"]:
        send(pid, birth, signal.SIGCONT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recover", type=Path)
    parser.add_argument("--seconds", type=float, default=1200)
    args = parser.parse_args()
    if args.recover:
        recover(args.recover)
        return
    (ROOT / "logs").mkdir(exist_ok=True)
    locks = []
    for app in (ROOT, ROOT.parent / "SlayTheSpireGeometryP1", ROOT.parent / "SlayTheSpireTouchR2"):
        if not (app / "logs").is_dir():
            continue
        lock = (app / "logs/session.lock").open("a+")
        locks.append(lock)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("An isolated probe is already active")
    menus = []
    for comm in Path("/proc").glob("[0-9]*/comm"):
        try:
            name = comm.read_text().strip()
            if name in ("java", "love", "love.aarch64", "retroarch"):
                raise RuntimeError("Close other games first")
            if name == "dmenu.bin":
                pid = int(comm.parent.name)
                state = (comm.parent / "stat").read_text().rsplit(")", 1)[1].split()[0]
                if state not in ("T", "t"):
                    menus.append([pid, identity(pid)])
        except FileNotFoundError:
            pass
    log = (ROOT / "logs/supervisor.log").open("w", buffering=1)
    state = dict(owner=os.getpid(), birth=identity(os.getpid()), menus=menus,
                 child=None, bridge=None, touch_previous=None)
    path = ROOT / "logs/recovery.json"
    def persist():
        temporary = ROOT / "logs/recovery.tmp"
        temporary.write_text(json.dumps(state))
        temporary.replace(path)
    def message(text):
        print(text, file=log, flush=True)
    requested = False
    def stop(*_):
        nonlocal requested
        requested = True
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)
    child = bridge = guardian = None
    guard = Devices(guard=True)
    inherited_locks = tuple(lock.fileno() for lock in locks)
    try:
        persist()
        guardian = subprocess.Popen([sys.executable, str(ROOT / "supervisor.py"), "--recover", str(path)],
                                    stdout=log, stderr=log, start_new_session=True,
                                    pass_fds=inherited_locks)
        for pid, birth in menus:
            send(pid, birth, signal.SIGSTOP)
        state["touch_previous"] = read_mode(log=message)
        persist()
        if not enable_mode(state["touch_previous"], log=message):
            raise RuntimeError("Explicit touch activation failed")
        env = os.environ.copy()
        env.update(RGDS_DIAGNOSTICS_DIR=str(ROOT / "logs"),
                   RGDS_CAPTURE_PATH=str(ROOT / "logs/capture.pam"),
                   RGDS_CAPTURE_REQUEST=str(ROOT / "logs/capture.request"),
                   RGDS_CAPTURE_FRAME="0", RGDS_FRAME_CSV=str(ROOT / f"logs/frames-{os.getpid()}.csv"))
        for key in ("LD_PRELOAD", "WRAPPED_PRELOAD"):
            env.pop(key, None)
        bridge = subprocess.Popen([sys.executable, str(ROOT / "touch_bridge.py")],
                                  stdout=log, stderr=log, start_new_session=True,
                                  pass_fds=inherited_locks)
        state["bridge"] = [bridge.pid, identity(bridge.pid)]
        persist()
        child = subprocess.Popen(["/bin/bash", str(ROOT / "game-launch.sh")],
                                 env=env, cwd=ROOT, stdout=log, stderr=log,
                                 start_new_session=True)
        state["child"] = [child.pid, identity(child.pid)]
        persist()
        started = time.monotonic()
        while child.poll() is None and not requested:
            now = time.monotonic()
            guard.poll(now)
            requested = guard.exit_held(now) or (args.seconds > 0 and now-started >= args.seconds)
            if bridge.poll() is not None:
                raise RuntimeError("Touch capture process stopped")
            time.sleep(.02)
        if requested:
            message("[r3-supervisor] independent stop requested")
        stop_runtime(state)
        message(f"[r3-supervisor] launcher_exit={child.wait()}")
    finally:
        stop_runtime(state)
        for process in (child, bridge):
            if process:
                process.wait()
        guard.close()
        restore_mode(state.get("touch_previous"), log=message)
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
