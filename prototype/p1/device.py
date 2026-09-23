"""Private SSH deployment/verification of this isolated, game-free probe only."""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import shlex
import time

import paramiko

ROOT = Path(__file__).resolve().parent
APP = "/mnt/sdcard/Ports/SlayTheSpireGeometryP1"
ENTRY = "/mnt/sdcard/Ports/Slay the Spire P1 Geometry.sh"
FILES = ("geometry.py", "device_input.py", "app.py", "supervisor.py", "launch.sh",
         "touch_mode.py", "test_geometry.py", "test_input.py", "test_touch_mode.py",
         "replay.json", "README.zh-CN.md")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("deploy", "run", "fetch", "status", "stop",
                                           "tests", "key", "touch", "freeze", "crash"))
    parser.add_argument("--host", default=os.getenv("RGDSPLUS_SSH_HOST"))
    parser.add_argument("--seconds", type=float, default=12)
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--code", type=int, default=304)
    parser.add_argument("--hold", type=float, default=0.12)
    parser.add_argument("--target", type=int, default=2)
    args = parser.parse_args()
    password = os.getenv("RGDSPLUS_SSH_PASSWORD") or getpass.getpass("SSH password: ")
    c = paramiko.SSHClient()
    c.load_system_host_keys()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(args.host, username="root", password=password, timeout=10,
              look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()

    def shell(command, timeout=40):
        _, out, err = c.exec_command(command, timeout=timeout)
        text, errors = out.read().decode(), err.read().decode()
        rc = out.channel.recv_exit_status()
        if rc:
            raise RuntimeError(f"exit={rc}\n{text}\n{errors}")
        return text + errors

    def remote_python(code):
        return shell("python3 -c " + shlex.quote(code))

    guard = f"""
import json, os, signal, sys, time
from pathlib import Path
sys.path.insert(0, {APP!r})
from supervisor import identity
state = json.loads(Path({APP + '/logs/session.json'!r}).read_text())
assert identity(state['owner']) == state['birth'], 'P1 supervisor not running'
pid, birth = state['child']
assert identity(pid) == birth, 'P1 render process not running'
assert {APP!r}.encode() in Path(f'/proc/{{pid}}/cmdline').read_bytes()
"""
    try:
        if args.action == "deploy":
            remote_python(f"""
from pathlib import Path
for path in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        parts = path.read_bytes().split(b'\\0')
        assert {APP + '/app.py'!r}.encode() not in parts, 'Close P1 before deployment'
    except FileNotFoundError:
        pass
""")
            shell(f"mkdir -p {APP}/logs")
            checksums = {}
            for name in FILES:
                path = ROOT / name
                if not path.exists():
                    continue
                sftp.put(str(path), APP + "/" + name)
                checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            sftp.put(str(ROOT / Path(ENTRY).name), ENTRY)
            with sftp.open(APP + "/manifest.json", "w") as stream:
                stream.write(json.dumps(dict(build="p1-geometry-20260920-aim3",
                                             files=checksums, game_assets=False)))
            shell("chmod +x " + shlex.quote(ENTRY) + f" {APP}/launch.sh")
            print("Deployed", APP, len(checksums), "source files; no game assets")
        elif args.action == "run":
            command = f"/bin/sh {shlex.quote(ENTRY)} --seconds {args.seconds} --capture"
            if args.replay:
                command += f" --replay {APP}/replay.json"
            if args.background:
                print(shell(f"nohup {command} >{APP}/logs/ssh.log 2>&1 </dev/null &"))
            else:
                print(shell(command, max(40, args.seconds + 15)))
                print(shell(f"cat {APP}/logs/latest.log"))
        elif args.action == "tests":
            print(shell(f"cd {APP} && python3 -m unittest discover -v"))
        elif args.action == "status":
            print(shell(f"cat {APP}/logs/state.json {APP}/logs/latest.log"))
            print(shell("ps -eo pid,stat,comm,args | tail -20"))
        elif args.action == "fetch":
            output = ROOT.parents[1] / "validation/p1-geometry"
            output.mkdir(parents=True, exist_ok=True)
            for item in sftp.listdir_attr(APP + "/logs"):
                if item.filename.endswith((".json", ".jsonl", ".log", ".ppm")):
                    sftp.get(APP + "/logs/" + item.filename, str(output / item.filename))
            print(output)
        elif args.action == "stop":
            print(remote_python(guard + "\nos.kill(state['owner'], signal.SIGTERM)\n"))
        elif args.action == "freeze":
            print(remote_python(guard + "\nos.kill(pid, signal.SIGSTOP)\n"))
        elif args.action == "crash":
            print(remote_python(guard + "\nos.kill(state['owner'], signal.SIGKILL)\n"))
        elif args.action == "key":
            assert args.code in (-16, 16, 304, 305, 306, 307, 308, 309, 310, 312, 314, 315)
            assert 0.03 <= args.hold <= 2.5
            print(remote_python(guard + f"""
import struct
path = next(p for p in Path('/sys/class/input').glob('event*/device/name')
            if p.read_text().strip() == 'ANBERNIC-rk3568-keys')
fd = os.open('/dev/input/' + path.parents[1].name, os.O_WRONLY)
ev = struct.Struct('@llHHi')
for value in (1, 0):
    kind = 3 if abs({args.code}) == 16 else 1
    code = abs({args.code})
    actual = -value if {args.code} == -16 else value
    os.write(fd, ev.pack(0, 0, kind, code, actual) + ev.pack(0, 0, 0, 0, 0))
    if value: time.sleep({args.hold})
os.close(fd)
"""))
        elif args.action == "touch":
            assert 0 <= args.target <= 4
            print(remote_python(guard + f"""
import struct
path = next(p for p in Path('/sys/class/input').glob('event*/device/name')
            if p.read_text().strip() == 'gt9xx-0')
fd = os.open('/dev/input/' + path.parents[1].name, os.O_WRONLY)
ev = struct.Struct('@llHHi')
def write(events):
    os.write(fd, b''.join(ev.pack(0, 0, *e) for e in events + [(0, 0, 0)]))
write([(3,47,0),(3,57,18001),(3,53,512),(3,54,590),(1,330,1)])
time.sleep(.15)
x = int(512 + ((120 + {args.target} * 196) - 512) * .3)
for step in range(1, 11):
    write([(3,53,int(512+(x-512)*step/10)),(3,54,int(590-317*step/10))])
    time.sleep(.04)
time.sleep(.15)
write([(3,57,-1),(1,330,0)])
os.close(fd)
"""))
    finally:
        sftp.close()
        c.close()


if __name__ == "__main__":
    main()
