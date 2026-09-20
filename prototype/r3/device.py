"""Private, fixed-directory R3 deployment and evidence collection."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shlex
import sys
import time
import xml.etree.ElementTree as ET

import paramiko
from launch_profile import configure

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "prototype/r3"
APP = "/mnt/sdcard/Ports/SlayTheSpireDualR3"
ENTRY = "Slay the Spire R3 Native UI.sh"
KEYS = {"a": (1,304,1), "b": (1,305,1), "x": (1,307,1), "y": (1,306,1),
        "l": (1,308,1), "r": (1,309,1), "select": (1,310,1), "start": (1,311,1),
        "l2": (1,314,1), "r2": (1,315,1), "left": (3,16,-1), "right": (3,16,1),
        "up": (3,17,-1), "down": (3,17,1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("deploy", "run", "status", "key", "shot", "stop",
                                          "logs", "audit", "touch-probe", "perf"))
    parser.add_argument("--seconds", type=int, default=1200)
    parser.add_argument("--fps", type=int, choices=(24, 30, 60), default=30)
    parser.add_argument("--heap-mb", type=int, choices=(128, 140, 160, 180), default=140)
    parser.add_argument("--initial-heap-mb", type=int, choices=(32, 64, 128), default=64)
    parser.add_argument("--gc", choices=("Serial", "G1", "Parallel"), default="Serial")
    parser.add_argument("--diagnostic-io", choices=("card", "ram"), default="ram")
    parser.add_argument("--keys", nargs="+", choices=KEYS, default=[])
    parser.add_argument("--hold-seconds", type=float, default=.12)
    parser.add_argument("--name", default="native-ui")
    args = parser.parse_args()
    if not .05 <= args.hold_seconds <= 3:
        parser.error("Hold must be between .05 and 3 seconds")
    if args.hold_seconds > .5 and args.keys != ["select"]:
        parser.error("Long injection is restricted to the independent Select exit")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.31.116", username="root", password=os.environ["RGDSPLUS_SSH_PASSWORD"],
                   timeout=12, look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    output = ROOT / "validation/r3-native-ui"
    output.mkdir(parents=True, exist_ok=True)
    def shell(command, timeout=60):
        _, out, err = client.exec_command(command, timeout=timeout)
        text = out.read().decode(errors="replace") + err.read().decode(errors="replace")
        if out.channel.recv_exit_status():
            raise RuntimeError(text)
        return text
    def remote(code, timeout=60):
        return shell("python3 -c " + shlex.quote(code), timeout)
    def read(path):
        with sftp.open(path, "rb") as stream:
            return stream.read()
    def write(path, data):
        with sftp.open(path, "wb") as stream:
            stream.write(data)
    def diagnostic_dir():
        try:
            recovery = json.loads(read(APP + "/logs/recovery.json"))
            path = recovery.get("runtime", APP + "/logs")
            if path != APP + "/logs" and not re.fullmatch("/tmp/rgds-sts-r3-[a-z0-9_]+", path):
                raise ValueError("Unexpected diagnostic directory")
            sftp.stat(path)
            return path
        except FileNotFoundError:
            return APP + "/logs"
    def state():
        result = {}
        directory = diagnostic_dir()
        for name in ("state.xml", "dual-state.xml"):
            try:
                root = ET.fromstring(read(directory + "/" + name))
                result[name] = {e.attrib["key"]: e.text for e in root.findall("entry")}
            except FileNotFoundError:
                result[name] = None
        return result
    guard = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, {APP!r})
from supervisor import identity
from rgds_exit import game_identity
app = Path({APP!r})
owned = json.loads((app/'logs/recovery.json').read_text())
assert identity(owned['owner']) == owned['birth'], 'No matching R3 supervisor'
log = Path((app/'logs/latest-path.txt').read_text().strip())
assert log.parent == app/'logs'
assert game_identity(Path(str(log)[:-4])), 'No matching R3 JVM'
for p in Path('/proc').glob('[0-9]*/comm'):
    try:
        if p.read_text().strip() == 'dmenu.bin':
            assert (p.parent/'stat').read_text().rsplit(')',1)[1].split()[0] in ('T','t')
    except FileNotFoundError: pass
"""
    try:
        if args.action == "deploy":
            print(remote(f"""
from pathlib import Path
import shutil
app = Path({APP!r})
assert app.resolve() == app
for p in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        parts = p.read_bytes().split(b'\\0')
        assert str(app/'supervisor.py').encode() not in parts, 'R3 active'
        assert b'java' != Path(parts[0].decode(errors='replace')).name.encode(), 'Close game'
    except (FileNotFoundError, IndexError): pass
source = Path('/tmp/rgds-sts-silent-01')
assert source.resolve() == source and (source/'saves/IRONCLAD.autosave').is_file()
app.mkdir(exist_ok=True)
(app/'logs').mkdir(exist_ok=True)
for name in ('desktop-1.0.jar','controller-injector.jar','texcompress-agent.jar',
             'libtexcompress.so','libastcenc-neon-shared.so','libwrap.so','libXrandr.so.2',
             'libgdx-controllers-desktop.so','libopenal.so','build-manifest.json',
             'slay.gptk','rgds-gamecontroller.txt','twitchconfig.txt'):
    dest = app/name
    if not dest.exists():
        shutil.copy2(source/name, dest)
build = 'cfad868ac8d65a88e71a0bf096fb09f78811e553effe0787c5309a655e081673-p0-single-3'
for relative in ('cache/builds/'+build, 'cache/texcache', 'betaPreferences', 'saves'):
    dest = app/relative
    if not dest.exists():
        shutil.copytree(source/relative, dest, ignore=shutil.ignore_patterns('pulse'))
print('Private R3 clone ready; production saves never copied')
""", 240))
            launch = configure((ROOT / "packaging/launch.sh").read_text())
            write(APP + "/game-launch.sh", launch.encode())
            mapping = {
                "rgds-dual-r3.jar": HERE/"build/rgds-dual-r3.jar",
                "librgds-dual.so": HERE/"build/librgds-dual.so",
                "rgds-input-agent.jar": ROOT/"platform/rgds-input-agent.jar",
                "rgds_exit.py": ROOT/"platform/rgds_exit.py",
                "run-java.sh": ROOT/"packaging/run-java.sh",
                "patch_safe.sh": ROOT/"platform/patch_safe.sh",
                "supervisor.py": HERE/"supervisor.py", "touch_bridge.py": HERE/"touch_bridge.py",
                "diagnostic_io.py": HERE/"diagnostic_io.py",
                "touch_mode.py": ROOT/"prototype/p1/touch_mode.py",
                "device_input.py": ROOT/"prototype/p1/device_input.py",
                "session_runtime.py": ROOT/"prototype/p1/supervisor.py",
            }
            hashes = {}
            for name, path in mapping.items():
                data = path.read_bytes()
                write(APP + "/" + name, data)
                hashes[name] = hashlib.sha256(data).hexdigest()
            write("/mnt/sdcard/Ports/" + ENTRY, (HERE/ENTRY).read_bytes())
            write(APP+"/r3-manifest.json", json.dumps(dict(build="r3-perf30-20260920-1",
                  renderer_base="r3-small-screen-20260920-3",
                  default_profile=dict(fps=30, initial_heap_mb=64, heap_mb=140,
                                       gc="Serial", diagnostic_io="ram"),
                  files=hashes, game_assets_in_adapter=False, touch_policy="capture-only")).encode())
            print(shell(f"chmod +x {APP}/game-launch.sh {APP}/run-java.sh {APP}/patch_safe.sh " +
                        shlex.quote("/mnt/sdcard/Ports/" + ENTRY)))
        elif args.action == "run":
            print(shell(f"nohup python3 {APP}/supervisor.py --seconds {args.seconds} "
                        f"--fps {args.fps} --heap-mb {args.heap_mb} --gc {args.gc} "
                        f"--initial-heap-mb {args.initial_heap_mb} "
                        f"--diagnostic-io {args.diagnostic_io} "
                        f">{APP}/logs/ssh.log 2>&1 </dev/null &"))
        elif args.action == "status":
            print(json.dumps(state(), ensure_ascii=False, indent=2))
            print(shell(f"tail -20 {APP}/logs/supervisor.log"))
            print(shell(f"if test -f {APP}/logs/latest-path.txt; then tail -25 \"$(cat {APP}/logs/latest-path.txt)\"; fi"))
        elif args.action == "key":
            before = state()
            print(remote(guard + f"""
import fcntl, os, struct, time
p = next(p for p in Path('/sys/class/input').glob('event*/device/name')
         if p.read_text().strip() == 'ANBERNIC-rk3568-keys')
fd = os.open('/dev/input/'+p.parents[1].name, os.O_RDWR)
try:
    bits=bytearray(96); fcntl.ioctl(fd,0x80604518,bits)
    assert not any(bits), 'Physical buttons held'
    for kind,code,value in {[KEYS[k] for k in args.keys]!r}:
        def event(value):
            os.write(fd, struct.pack('@llHHi',0,0,kind,code,value)+struct.pack('@llHHi',0,0,0,0,0))
        try:
            event(value); time.sleep({args.hold_seconds!r})
        finally:
            event(0)
        time.sleep(.7)
finally:
    os.close(fd)
"""))
            time.sleep(1.2)
            after = state()
            with (output/"controller-actions.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(dict(time_ns=time.time_ns(), source="evdev-injection",
                    keys=args.keys, hold_seconds=args.hold_seconds, before=before, after=after),
                    ensure_ascii=False) + "\n")
            print(json.dumps(after, ensure_ascii=False, indent=2))
        elif args.action == "touch-probe":
            before = state()
            touch_before = json.loads(read(diagnostic_dir() + "/touch-state.json"))
            print(remote(guard + """
import fcntl, os, struct, time
status=json.loads((Path(owned.get('runtime', str(app/'logs')))/'touch-state.json').read_text())
assert status['policy']=='capture-only' and status['focused']
assert all(d['grabbed'] and not d['contacts'] for d in status['devices'])
p=next(p for p in Path('/sys/class/input').glob('event*/device/name')
       if p.read_text().strip()=='gt9xx-0')
fd=os.open('/dev/input/'+p.parents[1].name,os.O_RDWR)
armed=False
def report(events):
    os.write(fd,b''.join(struct.pack('@llHHi',0,0,*e) for e in events+[(0,0,0)]))
try:
    slots=bytearray(24); fcntl.ioctl(fd,0x80184540+47,slots)
    count=struct.unpack('=6i',slots)[2]+1
    ids=bytearray(struct.pack(f'={count+1}i',57,*([-1]*count)))
    fcntl.ioctl(fd,0x8000450A|(len(ids)<<16),ids)
    assert all(v<0 for v in struct.unpack(f'={count+1}i',ids)[1:]), 'Real contact active'
    armed=True
    report([(3,47,0),(3,57,-1),(1,330,0)])
    time.sleep(.1)
    report([(3,47,0),(3,57,29001),(3,53,512),(3,54,384),(1,330,1)])
    time.sleep(.15)
finally:
    if armed: report([(3,47,0),(3,57,-1),(1,330,0)])
    os.close(fd)
"""))
            time.sleep(2)
            after = state()
            touch_after = json.loads(read(diagnostic_dir() + "/touch-state.json"))
            evidence = dict(source="evdev-injection", physical_verified=False,
                            before=before, after=after,
                            touch_before=touch_before, touch_after=touch_after)
            destination = output / f"touch-probe-{time.time_ns()}.json"
            destination.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            assert touch_after["actions"] - touch_before["actions"] == 2, "Expected one down/up"
            for key in ("energy.totalCount", "hand.count", "discardPile.count",
                        "player.currentHealth", "dungeon.screen"):
                assert before["state.xml"].get(key) == after["state.xml"].get(key), key
            print(destination)
            print("One captured down/up; gameplay unchanged; not physical touch acceptance")
        elif args.action == "stop":
            print(remote(f"""
import json, signal, sys
from pathlib import Path
sys.path.insert(0, {APP!r})
from supervisor import send
s=json.loads(Path({APP+'/logs/recovery.json'!r}).read_text())
send(s['owner'],s['birth'],signal.SIGTERM)
"""))
        elif args.action == "shot":
            from PIL import Image
            assert re.fullmatch("[a-z0-9-]+", args.name)
            assert not (output/(args.name+".png")).exists()
            remote(guard)
            directory = diagnostic_dir()
            request, capture = directory+"/capture.request", directory+"/capture.pam"
            for path in (request, capture):
                try: sftp.remove(path)
                except FileNotFoundError: pass
            time.sleep(.4)
            write(request, b"capture\n")
            until = time.monotonic()+15
            while time.monotonic() < until:
                try:
                    header, pixels = read(capture).split(b"ENDHDR\n",1)
                    fields=dict(l.split(b" ",1) for l in header.splitlines() if b" " in l)
                    width,height=int(fields[b"WIDTH"]),int(fields[b"HEIGHT"])
                    if len(pixels)==width*height*4: break
                except (FileNotFoundError,ValueError): pass
                time.sleep(.25)
            else: raise TimeoutError("No completed frame capture")
            image=Image.frombytes("RGBA",(width,height),pixels).convert("RGB")
            image.save(output/(args.name+".png"))
            if (width,height)==(2048,768):
                stacked=Image.new("RGB",(1024,1536))
                stacked.paste(image.crop((0,0,1024,768)),(0,0))
                stacked.paste(image.crop((1024,0,2048,768)),(0,768))
                stacked.save(output/(args.name+"-stacked.png"))
            (output/(args.name+"-state.json")).write_text(
                json.dumps(state(),ensure_ascii=False,indent=2), encoding="utf-8")
            sftp.remove(request)
            sftp.remove(capture)
            print(output/(args.name+"-stacked.png"))
        elif args.action == "logs":
            for directory in dict.fromkeys((APP+"/logs", diagnostic_dir())):
                for item in sftp.listdir_attr(directory):
                    if item.filename.endswith((".xml",".json",".jsonl",".log",".csv",".txt")):
                        sftp.get(directory+"/"+item.filename,str(output/item.filename))
            print(output)
        elif args.action == "perf":
            evidence = json.loads(remote(guard + """
import time
result = dict(time_ns=time.time_ns(), monotonic_ms=time.monotonic()*1000, files={})
paths = [Path('/proc')/name for name in
         ('meminfo','vmstat','stat','diskstats','mounts','pressure/memory','pressure/io','pressure/cpu')]
for p in Path('/proc').glob('[0-9]*/comm'):
    try:
        if p.read_text().strip() == 'java':
            paths += [p.parent/name for name in ('status','stat','smaps_rollup','io')]
    except FileNotFoundError: pass
for pattern in ('devices/system/cpu/cpu*/cpufreq/scaling_cur_freq',
                'class/devfreq/*/cur_freq','class/devfreq/*/load',
                'class/thermal/thermal_zone*/temp'):
    paths += list(Path('/sys').glob(pattern))
for p in paths:
    try: result['files'][str(p)] = p.read_text()
    except OSError: pass
print(json.dumps(result))
"""))
            destination = output/f"perf-{evidence['time_ns']}.json"
            destination.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            print(destination)
            for name, text in evidence["files"].items():
                if name.endswith(("smaps_rollup", "cur_freq", "/load", "/temp", "/memory", "/io")):
                    print(name, text)
        elif args.action == "audit":
            evidence = json.loads(remote(f"""
import fcntl, hashlib, json, time
from pathlib import Path
app=Path({APP!r})
result=dict(time_ns=time.time_ns(), processes=[], locks={{}}, hashes={{}})
result['tpctrl']=Path('/sys/class/anbernic_misc/tpctrl').read_text().strip()
result['memory']=Path('/proc/meminfo').read_text()
for p in Path('/proc').glob('[0-9]*/comm'):
    try:
        comm=p.read_text().strip()
        cmd=(p.parent/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
        if comm in ('java','dmenu.bin','weston','gptokeyb','portsCtrl.dge') or str(app) in cmd:
            if comm == 'python3' and '-c ' in cmd: continue
            result['processes'].append(dict(pid=int(p.parent.name),comm=comm,cmd=cmd,
                stat=(p.parent/'stat').read_text(),status=(p.parent/'status').read_text()))
    except FileNotFoundError: pass
for directory in ('SlayTheSpireDualR3','SlayTheSpireGeometryP1','SlayTheSpireTouchR2'):
    base=app.parent/directory
    path=base/'logs/session.lock'
    if path.exists():
        with path.open('r') as stream:
            try:
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                result['locks'][directory]='free'
            except BlockingIOError:
                result['locks'][directory]='held'
    for name in ('touch_mode.py','device_input.py','r3-manifest.json','manifest.json'):
        path=base/name
        if path.is_file(): result['hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
for name in ('rgds-input-agent.jar','librgds-sdl.so','saves/IRONCLAD.autosave'):
    path=app.parent/'SlayTheSpire'/name
    result['hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps(result))
"""))
            destination = output/f"audit-{evidence['time_ns']}.json"
            destination.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            print(destination)
            print(json.dumps(dict(tpctrl=evidence["tpctrl"], locks=evidence["locks"],
                processes=[dict(pid=p["pid"], comm=p["comm"]) for p in evidence["processes"]],
                hashes=evidence["hashes"]), indent=2))
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
