"""Private clean-install validation with no network or shared runtime images.

Uses a disposable card directory, a private mount/network namespace and the
public ZIP. Never clears the player's installed game, caches or shared libs.
Connection credentials are read from environment variables, never packaged.
"""

import argparse
import json
import os
from pathlib import Path
import shlex
import hashlib

import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/mnt/sdcard/.sts-offline-validation-20260924"
APP = REMOTE + "/Ports/Slay the Spire for RGDSplus"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "start", "status", "stop"))
    parser.add_argument("--jar", type=Path)
    args = parser.parse_args()
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(os.environ["RGDSPLUS_SSH_HOST"], username="root",
                   password=os.environ["RGDSPLUS_SSH_PASSWORD"], timeout=12,
                   look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    sftp.get_channel().settimeout(45)
    client.get_transport().set_keepalive(10)

    def upload(local, remote):
        # Firmware SFTP can stall with pipelined writes. Wait for each ACK;
        # a final hash checks the entire file, including any resumed prefix.
        try:
            offset = sftp.stat(remote).st_size
        except FileNotFoundError:
            offset = 0
        assert offset <= local.stat().st_size
        print(f"Transfer {local.name}: resume at {offset} bytes", flush=True)
        with local.open("rb") as src, sftp.open(remote, "r+b" if offset else "wb") as dst:
            src.seek(offset)
            dst.seek(offset)
            while chunk := src.read(4 * 1024 * 1024):
                dst.write(chunk)
                dst.stat()
                print(f"Transferred {src.tell()}/{local.stat().st_size}", flush=True)
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        run(f"""
from pathlib import Path
import hashlib
assert hashlib.sha256(Path({remote!r}).read_bytes()).hexdigest()=={digest!r}
print('Transferred file SHA-256 verified')
""")

    def run(script):
        command = "python3 -u -c " + shlex.quote(script)
        _, out, err = client.exec_command(command, timeout=180)
        text = out.read().decode("utf-8", errors="replace")
        errors = err.read().decode("utf-8", errors="replace")
        if out.channel.recv_exit_status():
            raise RuntimeError(text + errors)
        print(text + errors, flush=True)

    try:
        if args.action == "stage":
            if not args.jar or not args.jar.is_file():
                parser.error("--jar must point to the locally purchased game")
            run(f"""
from pathlib import Path
root=Path({REMOTE!r})
root.mkdir(exist_ok=True)
assert root.resolve()==root
assert not (root/'test-process.json').exists(), 'Refusing to replace a started validation'
""")
            print("Uploading public adapter ZIP", flush=True)
            upload(ROOT / "dist/Slay the Spire for RGDSplus.zip", REMOTE + "/adapter.zip")
            run(f"""
from pathlib import Path
import zipfile,hashlib,json
root=Path({REMOTE!r})
with zipfile.ZipFile(root/'adapter.zip') as z:
    for name in z.namelist():
        path=(root/name).resolve()
        assert root in path.parents
    z.extractall(root)
    manifest=json.loads(z.read('PACKAGE_MANIFEST.json'))
    for name,digest in manifest['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, name
(root/'empty-libs').mkdir(exist_ok=True)
print('Public ZIP extracted and all payload hashes verified')
""")
            print("Uploading purchased JAR (no prebuilt game/cache/saves)", flush=True)
            upload(args.jar, APP + "/desktop-1.0.jar")
            run(f"""
from pathlib import Path
import hashlib
p=Path({APP!r})
assert not (p/'cache').exists() and not (p/'saves').exists()
print('jar_sha256='+hashlib.sha256((p/'desktop-1.0.jar').read_bytes()).hexdigest())
""")
        elif args.action == "start":
            # This process becomes the ordinary packaged supervisor. Its
            # recovery child inherits isolation; the firmware remains online.
            program = f"""
import ctypes,os,json,subprocess
from pathlib import Path
root=Path({REMOTE!r})
app=Path({APP!r})
assert root.resolve()==root and app.resolve()==app
previous=root/'test-process.json'
if previous.exists():
    old=json.loads(previous.read_text()); proc=Path('/proc')/str(old['pid'])
    if proc.exists():
        stat=(proc/'stat').read_text().rsplit(')',1)[1].split()
        assert stat[0]=='Z' or stat[19]!=old['birth'], 'Previous validation is still running'
for comm in Path('/proc').glob('[0-9]*/comm'):
    try:
        assert comm.read_text().strip() not in ('java','love','love.aarch64','retroarch'), 'Close running games'
    except FileNotFoundError:
        pass
libc=ctypes.CDLL(None,use_errno=True)
assert libc.unshare(0x00020000|0x40000000)==0, ('unshare',ctypes.get_errno())
assert libc.mount(None,b'/',None,0x4000|0x40000,None)==0, ('private mounts',ctypes.get_errno())
shared=Path('/mnt/ports/PortMaster/libs')
assert shared.is_dir()
assert libc.mount(os.fsencode(root/'empty-libs'),os.fsencode(shared),None,4096,None)==0, ctypes.get_errno()
assert list(shared.iterdir())==[]
interfaces=[line.split(':',1)[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]]
assert interfaces==['lo'], interfaces
# Offline does not mean disabling local IPC. The touch bridge uses loopback;
# leave it available while there are still no external interfaces/routes.
subprocess.run(['ip','link','set','lo','up'],check=True)
os.environ.pop('SLAYTHESPIRE_JAVA_HOME',None)
os.environ.pop('LD_LIBRARY_PATH',None)
os.environ['SLAYTHESPIRE_PORTMASTER']='/mnt/ports/PortMaster'
os.environ['PULSE_SERVER']='unix:/tmp/pulse-socket'
sink=subprocess.check_output(['pactl','get-default-sink'],text=True).strip()
mute=subprocess.check_output(['pactl','get-sink-mute',sink],text=True).strip()
assert mute in ('Mute: yes','Mute: no'), mute
assert not (root/'pulse-restore.json').exists(), 'Restore previous sound state first'
(root/'pulse-restore.json').write_text(json.dumps({{'sink':sink,'mute':mute=='Mute: yes'}}))
subprocess.run(['pactl','set-sink-mute',sink,'1'],check=True)
os.environ['PULSE_SINK']=sink
record={{'pid':os.getpid(),'birth':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
        'network':os.readlink('/proc/self/ns/net'),'mounts':os.readlink('/proc/self/ns/mnt'),
        'shared_images_visible':False}}
(root/'test-process.json').write_text(json.dumps(record))
print(json.dumps(record),flush=True)
os.execv('/bin/sh',['sh',str(root/'Ports/Slay the Spire for RGDSplus.sh')])
"""
            command = (
                "nohup python3 -u -c " + shlex.quote(program) + " >"
                + shlex.quote(REMOTE + "/test-run.log") + " 2>&1 </dev/null & echo $!"
            )
            _, out, err = client.exec_command(command, timeout=15)
            print("Started isolated validation: " + out.read().decode() + err.read().decode())
        elif args.action == "status":
            run(f"""
from pathlib import Path
import json
root=Path({REMOTE!r}); app=Path({APP!r})
for f in (root/'test-process.json',root/'test-run.log',app/'logs/supervisor.log'):
    if f.exists(): print(str(f)+':\\n'+f.read_text(errors='replace')[-3000:])
latest=app/'logs/latest-path.txt'
if latest.exists():
    log=Path(latest.read_text().strip())
    lines=log.read_text(errors='replace').splitlines()
    selected=[s for s in lines if any(m in s for m in ('[preflight]','runtime/offline','[release]','frames=','Error','Exception','[launcher]'))]
    print('\\n'.join(selected[-25:]))
recovery=app/'logs/recovery.json'
if recovery.exists():
    runtime=Path(json.loads(recovery.read_text())['runtime'])
    for name in ('state.xml','dual-state.xml'):
        p=runtime/name
        if p.exists(): print(name+':\\n'+p.read_text()[-5000:])
""")
        else:
            run(f"""
import json,os,signal,time,subprocess
from pathlib import Path
root=Path({REMOTE!r})
record=json.loads((root/'test-process.json').read_text())
pid=record['pid']; proc=Path('/proc')/str(pid)
if proc.exists():
    assert (proc/'stat').read_text().rsplit(')',1)[1].split()[19]==record['birth'], 'PID reused'
    assert os.readlink(proc/'ns/mnt')==record['mounts']
    os.kill(pid,signal.SIGTERM)
    for _ in range(120):
        if not proc.exists() or (proc/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z': break
        time.sleep(.5)
    else: raise RuntimeError('Supervisor did not finish recovery')
print('Isolated session stopped through supervisor recovery')
print((root/'Ports/Slay the Spire for RGDSplus/logs/supervisor.log').read_text()[-1500:])
sound=root/'pulse-restore.json'
if sound.exists():
    original=json.loads(sound.read_text())
    env=dict(os.environ,PULSE_SERVER='unix:/tmp/pulse-socket')
    subprocess.run(['pactl','set-sink-mute',original['sink'],
                    '1' if original['mute'] else '0'],env=env,check=True)
    sound.unlink()
print('Previous mute state restored; volume unchanged')
""")
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
