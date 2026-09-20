"""Independent, session-scoped RGDSplus long-press exit guard (Linux stdlib)."""

import argparse
import glob
import os
from pathlib import Path
import select
import signal
import struct
import time


EVENT = struct.Struct("@llHHi")
HOLD_SECONDS = 1.5
DEVICES = {
    "ANBERNIC-rk3568-keys": {310, 312},  # Balatro b6 Back and b8 Guide.
    "adc-keys": {158},  # Dedicated KEY_BACK.
}


class Hold:
    def __init__(self):
        self.since = {}

    def event(self, source, code, value, now):
        key = (source, code)
        if value == 1:
            self.since.setdefault(key, now)
        elif value == 0:
            self.since.pop(key, None)

    def cancel(self, source):
        self.since = {k: v for k, v in self.since.items() if k[0] != source}

    def expired(self, now):
        return any(now - start >= HOLD_SECONDS for start in self.since.values())


def identity(pid):
    try:
        # comm can contain spaces and parentheses; starttime is field 22.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return fields[19]
    except (OSError, IndexError):
        return None


def game_identity(session):
    try:
        pid = int(Path(str(session) + ".java.pid").read_text())
        args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        app = session.parent.parent
        jar = args[args.index(b"-jar") + 1].decode()
        if Path(args[0].decode()).name != "java":
            return None
        if not Path(jar).is_relative_to(app / "cache" / "builds"):
            return None
        if jar.rsplit("/", 1)[-1] != "desktoppatched.jar":
            return None
        # Match this session, not just another JVM using the same application.
        if f"-XX:ErrorFile={session}.hs_err_%p.log".encode() not in args:
            return None
        birth = identity(pid)
        return (pid, birth) if birth else None
    except (OSError, ValueError, IndexError):
        return None


def terminate(target, grace=3.0):
    pid, birth = target
    if identity(pid) != birth:
        return
    print(f"[exit-guard] TERM game pid={pid}", flush=True)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    until = time.monotonic() + grace
    while identity(pid) == birth and time.monotonic() < until:
        time.sleep(0.05)
    if identity(pid) == birth:
        print(f"[exit-guard] KILL unresponsive game pid={pid}", flush=True)
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run(session, owner):
    import fcntl

    owner_birth = identity(owner)
    if owner_birth is None:
        raise RuntimeError("launcher is not alive")
    devices = {}
    hold = Hold()
    target = None
    next_scan = 0.0
    requested = False

    def close_device(fd):
        hold.cancel(fd)
        os.close(fd)
        del devices[fd]

    try:
        while identity(owner) == owner_birth:
            now = time.monotonic()
            if target is None:
                target = game_identity(session)
            elif identity(target[0]) != target[1]:
                return
            if now >= next_scan:
                next_scan = now + 2
                paths = {item[0] for item in devices.values()}
                for namefile in glob.glob("/sys/class/input/event*/device/name"):
                    name = Path(namefile).read_text().strip()
                    if name not in DEVICES:
                        continue
                    path = "/dev/input/" + Path(namefile).parents[1].name
                    if path in paths:
                        continue
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    devices[fd] = (path, DEVICES[name], set())
                    # Ignore already-held keys until their first release.
                    bits = bytearray(96)
                    fcntl.ioctl(fd, 0x80604518, bits)
                    devices[fd][2].update(k for k in DEVICES[name]
                                          if bits[k // 8] & (1 << (k % 8)))
                    print(f"[exit-guard] watching {path} {name}", flush=True)
                if devices:
                    Path(str(session) + ".exit-ready").touch()
            ready, _, _ = select.select(list(devices), [], [], 0.05)
            for fd in ready:
                try:
                    data = os.read(fd, EVENT.size * 64)
                except OSError:
                    close_device(fd)
                    continue
                if not data:
                    close_device(fd)
                    continue
                _, codes, blocked = devices[fd]
                for _, _, kind, code, value in EVENT.iter_unpack(data):
                    if kind == 0 and code == 3:  # SYN_DROPPED
                        hold.cancel(fd)
                        blocked.update(codes)
                    elif kind == 1 and code in codes:
                        if code in blocked:
                            if value == 0:
                                blocked.remove(code)
                            continue
                        hold.event(fd, code, value, time.monotonic())
            if not requested and hold.expired(time.monotonic()):
                requested = True
                Path(str(session) + ".exit-requested").touch()
                print("[exit-guard] long press: exit requested", flush=True)
            if requested and target:
                terminate(target)
                return
    finally:
        for fd in list(devices):
            close_device(fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--owner", type=int)
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if args.stop:
        target = game_identity(args.session)
        if target:
            terminate(target)
    elif args.owner:
        run(args.session, args.owner)
    else:
        parser.error("--owner is required unless --stop is used")


if __name__ == "__main__":
    main()
