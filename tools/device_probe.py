"""Private testing only: read state, press buttons and capture an isolated session."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
import xml.etree.ElementTree as ET

import paramiko


KEYS = {
    "a": (1, 304, 1), "b": (1, 305, 1), "x": (1, 307, 1), "y": (1, 306, 1),
    "l": (1, 308, 1), "r": (1, 309, 1), "select": (1, 310, 1),
    "start": (1, 311, 1), "l2": (1, 314, 1), "r2": (1, 315, 1),
    "left": (3, 16, -1), "right": (3, 16, 1),
    "up": (3, 17, -1), "down": (3, 17, 1),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("RGDSPLUS_SSH_HOST"))
    parser.add_argument("--app", default="/tmp/rgds-sts-silent-01")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    key = sub.add_parser("key")
    key.add_argument("keys", nargs="+", choices=sorted(KEYS))
    key.add_argument("--hold-ms", type=int, default=140)
    shot = sub.add_parser("shot")
    shot.add_argument("name")
    sub.add_parser("logs")
    args = parser.parse_args()
    if not re.fullmatch(r"/tmp/rgds-sts-[a-z0-9-]+", args.app):
        parser.error("Only explicitly isolated /tmp/rgds-sts-* installations are supported")
    if args.command == "shot" and not re.fullmatch(r"[a-z0-9-]+", args.name):
        parser.error("Screenshot names must contain lowercase letters, digits or hyphens")
    if args.command == "key" and not 20 <= args.hold_ms <= 500:
        parser.error("--hold-ms must be between 20 and 500")

    password = os.getenv("RGDSPLUS_SSH_PASSWORD") or getpass.getpass("Device SSH password: ")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username="root", password=password, timeout=12,
                   look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    output = Path(__file__).resolve().parents[1] / "validation" / Path(args.app).name
    output.mkdir(parents=True, exist_ok=True)

    def shell(command):
        _, stdout, stderr = client.exec_command(command, timeout=30)
        text, errors = stdout.read().decode(), stderr.read().decode()
        if stdout.channel.recv_exit_status():
            raise RuntimeError(text + errors)
        return text

    def state():
        with sftp.open(args.app + "/logs/state.xml") as stream:
            root = ET.fromstring(stream.read())
        return {item.attrib["key"]: item.text for item in root.findall("entry")}

    try:
        preflight = f"""
from pathlib import Path
import sys
app=Path({args.app!r})
assert app.resolve() == app, 'isolated app must not be a symlink'
sys.path.insert(0,str(app))
import rgds_exit
log=Path((app/'logs/latest-path.txt').read_text().strip())
assert rgds_exit.game_identity(Path(str(log)[:-4])), 'no matching live game session'
for proc in Path('/proc').glob('[0-9]*/comm'):
 try:
  if proc.read_text().strip()=='dmenu.bin':
   assert proc.with_name('stat').read_text().rsplit(')',1)[1].split()[0] in ('T','t'), 'menu not paused'
 except FileNotFoundError: pass
"""
        shell("python3 - <<'PY'\n" + preflight + "\nPY")
        if args.command == "key":
            before = state()
            script = preflight + f"""
import os,struct,time,fcntl
paths=[p for p in Path('/sys/class/input').glob('event*/device/name')
       if p.read_text().strip()=='ANBERNIC-rk3568-keys']
assert len(paths)==1
fd=os.open('/dev/input/'+paths[0].parents[1].name,os.O_RDWR)
try:
 bits=bytearray(96);fcntl.ioctl(fd,0x80604518,bits)
 assert not any(bits), 'release physical buttons first'
 for kind,code,value in { [KEYS[k] for k in args.keys]!r}:
  def event(v):
   os.write(fd,struct.pack('@llHHi',0,0,kind,code,v))
   os.write(fd,struct.pack('@llHHi',0,0,0,0,0))
  try: event(value);time.sleep({args.hold_ms / 1000!r})
  finally: event(0)
  time.sleep(.45)
finally: os.close(fd)
"""
            shell("python3 - <<'PY'\n" + script + "\nPY")
            time.sleep(1.1)
            after = state()
            with (output / "actions.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"keys": args.keys, "hold_ms": args.hold_ms,
                                         "before": before, "after": after}) + "\n")
            print(json.dumps(after, ensure_ascii=False, indent=2))
        elif args.command == "status":
            print(json.dumps(state(), ensure_ascii=False, indent=2))
        elif args.command == "shot":
            from PIL import Image
            local = output / (args.name + ".png")
            if local.exists():
                raise FileExistsError(local)
            request, capture = args.app + "/logs/capture.request", args.app + "/logs/capture.pam"
            for remote in (request, capture):
                try: sftp.remove(remote)
                except FileNotFoundError: pass
            time.sleep(.4)
            with sftp.open(request, "w") as stream:
                stream.write("capture\n")
            until = time.monotonic() + 12
            while time.monotonic() < until:
                try:
                    with sftp.open(capture, "rb") as stream:
                        data = stream.read()
                    header, pixels = data.split(b"ENDHDR\n", 1)
                    fields = dict(line.split(b" ", 1) for line in header.splitlines() if b" " in line)
                    width, height = int(fields[b"WIDTH"]), int(fields[b"HEIGHT"])
                    if len(pixels) == width * height * 4: break
                except (FileNotFoundError, ValueError): pass
                time.sleep(.2)
            else:
                raise TimeoutError("No complete capture; check the rendering thread")
            Image.frombytes("RGBA", (width, height), pixels).convert("RGB").save(local)
            sftp.remove(request)
            sftp.remove(capture)
            print(local)
        else:
            with sftp.open(args.app + "/logs/latest-path.txt") as stream:
                log = stream.read().decode().strip()
            for remote, name in [(log, "game.log"), (log[:-4] + ".resources.log", "resources.log"),
                                 (args.app + "/logs/frames.csv", "frames.csv")]:
                sftp.get(remote, str(output / name))
            print(shell("tail -16 " + shlex.quote(log)))
            print(output)
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
