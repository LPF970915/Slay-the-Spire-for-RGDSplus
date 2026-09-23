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
KEYS = {"a": (1,304,1), "b": (1,305,1), "x": (1,307,1), "y": (1,306,1),
        "l": (1,308,1), "r": (1,309,1), "select": (1,310,1), "start": (1,311,1),
        "l2": (1,314,1), "r2": (1,315,1), "left": (3,16,-1), "right": (3,16,1),
        "up": (3,17,-1), "down": (3,17,1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("RGDSPLUS_SSH_HOST"))
    parser.add_argument("action", choices=("deploy", "run", "status", "key", "shot", "stop",
                                          "logs", "audit", "touch-probe", "touch-tap", "perf", "page", "reset-review"))
    parser.add_argument("--variant", choices=("r3", "r4", "review"), default="r3")
    parser.add_argument("--page-probe", action="store_true")
    parser.add_argument("--page", choices=("cards", "relics", "potions", "stats", "history",
                                         "custom", "character", "inputs", "patch", "credits",
                                         "map", "deck", "settings"))
    parser.add_argument("--scene", choices=[f"u{i:02}" for i in range(1, 34)])
    parser.add_argument("--seconds", type=int, default=1200)
    parser.add_argument("--fps", type=int, choices=(24, 30, 60), default=30)
    parser.add_argument("--heap-mb", type=int, choices=(128, 140, 160, 180))
    parser.add_argument("--initial-heap-mb", type=int, choices=(32, 64, 128))
    parser.add_argument("--gc", choices=("Serial", "G1", "Parallel"), default="Serial")
    parser.add_argument("--jit-tier", type=int, choices=(1, 4))
    parser.add_argument("--diagnostic-io", choices=("card", "ram"), default="ram")
    parser.add_argument("--keys", nargs="+", choices=KEYS, default=[])
    parser.add_argument("--hold-seconds", type=float, default=.12)
    parser.add_argument("--name", default="native-ui")
    sound = parser.add_mutually_exclusive_group()
    sound.add_argument("--audio", action="store_true")
    sound.add_argument("--silent", action="store_true")
    parser.add_argument("--touch-live", action="store_true")
    parser.add_argument("--x", type=int, default=512)
    parser.add_argument("--y", type=int, default=384)
    args = parser.parse_args()
    if args.heap_mb is None:
        args.heap_mb = 140 if args.variant == "r3" else 128
    if args.initial_heap_mb is None:
        args.initial_heap_mb = 64 if args.variant == "r3" else 32
    if args.jit_tier is None:
        args.jit_tier = 4 if args.variant == "r3" else 1
    if args.variant == "review":
        APP = "/mnt/sdcard/Ports/SlayTheSpireDualR4Review"
    elif args.variant == "r4":
        APP = "/mnt/sdcard/Ports/Slay the Spire for RGDSplus"
    else:
        APP = "/mnt/sdcard/Ports/SlayTheSpireDualR3"
    ENTRY = "Slay the Spire for RGDSplus.sh" if args.variant == "r4" else "Slay the Spire R3 Native UI.sh"
    if (args.page_probe or args.action == "page") and args.variant not in ("r4", "review"):
        parser.error("Gallery probe is restricted to the separate R4 clone")
    if args.scene and args.variant != "review":
        parser.error("Specimens require --variant review")
    if args.action == "reset-review" and args.variant != "review":
        parser.error("Only the disposable review clone can reset its fixtures")
    if args.action == "page" and not (args.page or args.scene):
        parser.error("--page is required")
    if not .05 <= args.hold_seconds <= 3:
        parser.error("Hold must be between .05 and 3 seconds")
    if args.hold_seconds > .5 and args.keys != ["select"]:
        parser.error("Long injection is restricted to the independent Select exit")
    if not 0 <= args.x <= 1024 or not 0 <= args.y <= 768:
        parser.error("Touch injection uses lower-local 1024x768 coordinates")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username="root", password=os.environ["RGDSPLUS_SSH_PASSWORD"],
                   timeout=12, look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    output = ROOT / ("validation/r4-review" if args.variant == "review" else
                     "validation/r4-all-pages" if args.variant == "r4" else "validation/r3-native-ui")
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
source = Path({'/mnt/sdcard/Ports/Slay the Spire for RGDSplus' if args.variant == 'review' else '/mnt/sdcard/Ports/SlayTheSpireDualR3' if args.variant == 'r4' else '/tmp/rgds-sts-silent-01'!r})
assert source.resolve() == source and (source/'desktop-1.0.jar').is_file() and (source/'saves').is_dir()
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
print('Private test clone ready; existing saves never overwritten')
""", 240))
            launch = configure((ROOT / "packaging/launch.sh").read_text(encoding="utf-8"))
            write(APP + "/game-launch.sh", launch.encode())
            mapping = {
                "rgds-dual-r3.jar": HERE/"build/rgds-dual-r3.jar",
                "librgds-dual.so": HERE/"build/librgds-dual.so",
                "rgds-input-agent.jar": ROOT/"platform/rgds-input-agent.jar",
                "rgds_exit.py": ROOT/"platform/rgds_exit.py",
                "run-java.sh": ROOT/"packaging/run-java.sh",
                "patch_safe.sh": ROOT/"platform/patch_safe.sh",
                "supervisor.py": HERE/"supervisor.py", "touch_bridge.py": HERE/"touch_bridge.py",
                "touch_transport.py": HERE/"touch_transport.py",
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
            if args.variant != "review":
                write("/mnt/sdcard/Ports/" + ENTRY, (HERE/ENTRY).read_bytes())
            write(APP+"/r3-manifest.json", json.dumps(dict(build="r4-interface-20260923-13",
                  renderer_base="r3-small-screen-20260920-3",
                  default_profile=dict(fps=30, initial_heap_mb=64 if args.variant == "r3" else 32,
                                       heap_mb=140 if args.variant == "r3" else 128,
                                       jit_tier=4 if args.variant == "r3" else 1,
                                       gc="Serial", diagnostic_io="ram"),
                  files=hashes, game_assets_in_adapter=False,
                  touch_policy="native-lower-pointer" if args.variant == "r4" else "capture-only",
                  audio_enabled=args.variant == "r4")).encode())
            chmod_targets = [APP + "/game-launch.sh", APP + "/run-java.sh", APP + "/patch_safe.sh"]
            if args.variant != "review":
                chmod_targets.append("/mnt/sdcard/Ports/" + ENTRY)
            print(shell("chmod +x " + " ".join(shlex.quote(path) for path in chmod_targets)))
        elif args.action == "reset-review":
            print(remote(f"""
import shutil, time
from pathlib import Path
app = Path({APP!r})
assert app.name == 'SlayTheSpireDualR4Review' and app.resolve() == app
for p in Path('/proc').glob('[0-9]*/comm'):
    try: assert p.read_text().strip() != 'java', 'Close game before fixture reset'
    except FileNotFoundError: pass
archive = app/'logs'/('fixture-save-'+str(time.time_ns()))
archive.mkdir()
for name in ('saves', 'betaPreferences'):
    dest = app/name
    assert dest.resolve().parent == app
    if dest.exists(): dest.rename(archive/name)
    shutil.copytree(app.parent/'Slay the Spire for RGDSplus'/name, dest)
print('Archived disposable specimen saves, copied unchanged R4 test baseline')
"""))
        elif args.action == "run":
            print(shell("nohup python3 " + shlex.quote(APP + "/supervisor.py")
                        + f" --seconds {args.seconds} "
                        f"--fps {args.fps} --heap-mb {args.heap_mb} --gc {args.gc} "
                        f"--initial-heap-mb {args.initial_heap_mb} "
                        f"--jit-tier {args.jit_tier} "
                        f"--diagnostic-io {args.diagnostic_io} "
                        f"{'--page-probe ' if args.page_probe else ''}"
                        f"{'--review ' if args.variant == 'review' else ''}"
                        f"{'--audio ' if args.audio else ''}"
                        f"{'--silent ' if args.silent else ''}"
                        f"{'--touch-live ' if args.touch_live else ''}"
                        + " >" + shlex.quote(APP + "/logs/ssh.log") + " 2>&1 </dev/null &"))
        elif args.action == "page":
            remote(guard)
            directory = diagnostic_dir()
            result_path = directory + "/page-result.txt"
            try: sftp.remove(result_path)
            except FileNotFoundError: pass
            request = directory + "/page.request"
            write(request + ".tmp", (args.scene or args.page).encode())
            sftp.posix_rename(request + ".tmp", request)
            until = time.monotonic() + 30
            while time.monotonic() < until:
                try:
                    result = read(result_path).decode()
                    break
                except FileNotFoundError:
                    time.sleep(.25)
            else:
                raise TimeoutError("No gallery response; start R4 with --page-probe")
            (output / f"page-{time.time_ns()}.txt").write_text(result, encoding="utf-8")
            print(result)
            if "\nopened\n" not in result:
                raise RuntimeError("Gallery request rejected")
        elif args.action == "status":
            print(json.dumps(state(), ensure_ascii=False, indent=2))
            supervisor_log = shlex.quote(APP + "/logs/supervisor.log")
            latest_log = shlex.quote(APP + "/logs/latest-path.txt")
            print(shell(f"tail -20 {supervisor_log}"))
            print(shell(f"if test -f {latest_log}; then tail -25 \"$(cat {latest_log})\"; fi"))
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
        elif args.action in ("touch-probe", "touch-tap"):
            before = state()
            touch_before = json.loads(read(diagnostic_dir() + "/touch-state.json"))
            tap = args.action == "touch-tap"
            policy = "native-lower-pointer" if tap else "capture-only"
            print(remote(guard + f"""
import fcntl, os, struct, time
status=json.loads((Path(owned.get('runtime', str(app/'logs')))/'touch-state.json').read_text())
assert status['policy']=={policy!r} and status['focused']
""" + """
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
""" + f"""
    report([(3,47,0),(3,57,29001),(3,53,{args.x}),(3,54,{args.y}),(1,330,1)])
""" + """
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
            if not tap:
                for key in ("energy.totalCount", "hand.count", "discardPile.count",
                            "player.currentHealth", "dungeon.screen"):
                    assert before["state.xml"].get(key) == after["state.xml"].get(key), key
            print(destination)
            print(json.dumps(after, ensure_ascii=False, indent=2))
            print("One injected down/up; not physical touch acceptance")
        elif args.action == "stop":
            print(remote(f"""
import fcntl, json, signal, sys, time
from pathlib import Path
sys.path.insert(0, {APP!r})
from supervisor import send
s=json.loads(Path({APP+'/logs/recovery.json'!r}).read_text())
send(s['owner'],s['birth'],signal.SIGTERM)
until = time.monotonic() + 45
with Path({APP+'/logs/session.lock'!r}).open('a+') as lock:
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= until:
                raise TimeoutError('Supervisor recovery has not released its session lock')
            time.sleep(.2)
print('Session stopped and recovery lock released')
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
result=dict(time_ns=time.time_ns(), processes=[], locks={{}}, hashes={{}}, missing_baseline_files=[])
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
for directory in ('SlayTheSpireDualR3','Slay the Spire for RGDSplus','SlayTheSpireDualR4','SlayTheSpireDualR4Review','SlayTheSpireGeometryP1','SlayTheSpireTouchR2'):
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
    if path.is_file():
        result['hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        result['missing_baseline_files'].append(str(path))
for directory in ('SlayTheSpireDualR3', 'Slay the Spire for RGDSplus', 'SlayTheSpireDualR4'):
    for path in (app.parent/directory/'saves').glob('*'):
        if path.is_file():
            result['hashes'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps(result))
"""))
            destination = output/f"audit-{evidence['time_ns']}.json"
            destination.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            print(destination)
            print(json.dumps(dict(tpctrl=evidence["tpctrl"], locks=evidence["locks"],
                processes=[dict(pid=p["pid"], comm=p["comm"]) for p in evidence["processes"]],
                missing_baseline_files=evidence["missing_baseline_files"],
                hashes=evidence["hashes"]), indent=2))
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
