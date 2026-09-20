"""Device actions scoped exclusively to the R2 probe and its owned process IDs."""

import argparse
import getpass
import json
import os
from pathlib import Path
import shlex
import sys
import time
import zipfile

import paramiko

from make_package import ROOT, HERE, BUILD, PREFIX, ENTRY

APP = "/mnt/sdcard/Ports/SlayTheSpireTouchR2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("deploy", "run", "status", "fetch", "stop",
                                           "tests", "inject-grid", "key", "freeze", "crash"))
    parser.add_argument("--host", default="192.168.31.116")
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--source", choices=("physical-unconfirmed", "model-replay", "evdev-injection"),
                        default="physical-unconfirmed")
    parser.add_argument("--mode", choices=("grid", "drag"), default="grid")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--code", type=int, default=310)
    parser.add_argument("--hold", type=float, default=1.8)
    args = parser.parse_args()
    password = os.getenv("RGDSPLUS_SSH_PASSWORD") or getpass.getpass("SSH password: ")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username="root", password=password, timeout=10,
                   look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()

    def shell(command, timeout=40):
        _, out, err = client.exec_command(command, timeout=timeout)
        text, errors = out.read().decode(), err.read().decode()
        if out.channel.recv_exit_status():
            raise RuntimeError(text + errors)
        return text + errors

    def python(code):
        return shell("python3 -c " + shlex.quote(code))

    guard = f"""
import json, os, signal, sys, time
from pathlib import Path
sys.path.insert(0, {APP!r})
from supervisor import identity
state = json.loads(Path({APP + '/logs/session.json'!r}).read_text())
assert identity(state['owner']) == state['birth'], 'R2 supervisor not active'
pid, birth = state['child']
assert identity(pid) == birth, 'R2 renderer not active'
assert {APP + '/app.py'!r}.encode() in Path(f'/proc/{{pid}}/cmdline').read_bytes().split(b'\\0')
"""
    try:
        if args.action == "deploy":
            python(f"""
from pathlib import Path
for path in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        parts = path.read_bytes().split(b'\\0')
        assert {APP + '/app.py'!r}.encode() not in parts, 'R2 still running'
        assert {APP + '/supervisor.py'!r}.encode() not in parts, 'R2 supervisor still active'
    except FileNotFoundError:
        pass
""")
            shell(f"mkdir -p {APP}/logs")
            with zipfile.ZipFile(ROOT / "dist/SlayTheSpire_R2_TouchProbe_game-free.zip") as archive:
                for name in archive.namelist():
                    if name.startswith(PREFIX):
                        relative = name[len(PREFIX):]
                        assert "/" not in relative and relative not in (".", "..")
                        dest = APP + "/" + relative
                    else:
                        assert name == "Ports/" + ENTRY
                        dest = "/mnt/sdcard/Ports/" + ENTRY
                    with sftp.open(dest, "w") as stream:
                        stream.write(archive.read(name))
            for name in ("test_probe.py",):
                sftp.put(str(HERE / name), APP + "/" + name)
            replay = ROOT / "dist/r2-replay.json"
            if replay.exists():
                sftp.put(str(replay), APP + "/replay.json")
            shell(f"chmod +x {APP}/launch.sh " + shlex.quote("/mnt/sdcard/Ports/" + ENTRY))
            print("Installed", BUILD, "without changing R1")
        elif args.action == "run":
            if args.replay and args.source != "model-replay":
                parser.error("--replay requires --source model-replay")
            command = (f"/bin/sh {shlex.quote('/mnt/sdcard/Ports/' + ENTRY)} "
                       f"--seconds {args.seconds} --source {args.source} --mode {args.mode}")
            if args.replay:
                command += f" --replay {APP}/replay.json"
            if args.capture:
                command += " --capture"
            if args.background:
                print(shell(f"nohup {command} >{APP}/logs/ssh.log 2>&1 </dev/null &"))
            else:
                print(shell(command, max(40, args.seconds + 15)))
                print(shell(f"cat {APP}/logs/latest.log"))
        elif args.action == "status":
            print(shell(f"cat {APP}/logs/state.json {APP}/logs/latest.log"))
            print(shell("pgrep -a python3 || true"))
        elif args.action == "tests":
            print(shell(f"cd {APP} && python3 -m unittest test_probe -v"))
        elif args.action == "fetch":
            output = ROOT / "validation/r2-probe"
            output.mkdir(parents=True, exist_ok=True)
            for item in sftp.listdir_attr(APP + "/logs"):
                if item.filename.endswith((".json", ".jsonl", ".log", ".ppm")):
                    local = output / item.filename
                    if item.filename.endswith(".ppm") and local.exists() and local.stat().st_size == item.st_size:
                        continue
                    sftp.get(APP + "/logs/" + item.filename, str(local))
            print(output)
        elif args.action in ("stop", "freeze", "crash"):
            command = {"stop": "os.kill(state['owner'], signal.SIGTERM)",
                       "freeze": "os.kill(pid, signal.SIGSTOP)",
                       "crash": "os.kill(state['owner'], signal.SIGKILL)"}[args.action]
            print(python(guard + "\n" + command))
        elif args.action == "key":
            if args.code not in (305, 307, 308, 309, 310) or not .03 <= args.hold <= 2.5:
                parser.error("Unsupported key or hold")
            print(python(guard + f"""
import struct
p = next(p for p in Path('/sys/class/input').glob('event*/device/name')
         if p.read_text().strip() == 'ANBERNIC-rk3568-keys')
fd = os.open('/dev/input/' + p.parents[1].name, os.O_WRONLY)
ev = struct.Struct('@llHHi')
for value in (1, 0):
    os.write(fd, ev.pack(0, 0, 1, {args.code}, value) + ev.pack(0, 0, 0, 0, 0))
    if value: time.sleep({args.hold})
os.close(fd)
"""))
        elif args.action == "inject-grid":
            print(python(guard + f"""
import struct
latest = json.loads(Path({APP + '/logs/state.json'!r}).read_text())
assert latest['probe']['source'] == 'evdev-injection', 'Never inject into physical measurement'
assert latest['probe']['samples'] == 0, 'Fresh measurement required'
p = next(p for p in Path('/sys/class/input').glob('event*/device/name')
         if p.read_text().strip() == 'gt9xx-0')
fd = os.open('/dev/input/' + p.parents[1].name, os.O_WRONLY)
ev = struct.Struct('@llHHi')
def report(events):
    os.write(fd, b''.join(ev.pack(0, 0, *e) for e in events + [(0,0,0)]))
try:
    for index in range(27):
        x = (16,512,1008)[index % 3]
        y = (16,384,752)[index % 9 // 3]
        assert identity(pid) == birth and identity(state['owner']) == state['birth']
        report([(3,47,0),(3,57,19000+index),(3,53,x),(3,54,y),(1,330,1)])
        time.sleep(.10)
        report([(3,57,-1),(1,330,0)])
        time.sleep(.12)
finally:
    report([(3,47,0),(3,57,-1),(1,330,0)])
    os.close(fd)
"""))
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
