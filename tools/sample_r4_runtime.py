"""Read-only bounded performance and optional output-monitor audio measurements."""

import argparse
import csv
import io
import json
import os
from pathlib import Path
import shlex
import time
import paramiko
from analyze_frames import summarize

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r'''
import array, json, math, subprocess, sys, time
from pathlib import Path
app=Path('/mnt/sdcard/Ports/SlayTheSpireDualR4Review')
sys.path.insert(0,str(app))
from supervisor import identity
from rgds_exit import game_identity
owned=json.loads((app/'logs/recovery.json').read_text())
assert identity(owned['owner'])==owned['birth']
log=Path((app/'logs/latest-path.txt').read_text().strip())
assert log.parent==app/'logs' and game_identity(Path(str(log)[:-4]))
directory=Path(owned['runtime'])
pid=next(p.parent for p in Path('/proc').glob('[0-9]*/comm') if p.read_text().strip()=='java')
def read(path):
    try: return path.read_text()
    except OSError: return ''
def sample():
    return dict(t=time.monotonic(),vm=read(Path('/proc/vmstat')),mem=read(Path('/proc/meminfo')),
                status=read(pid/'status'),stat=read(pid/'stat'))
a=sample(); time.sleep(seconds); b=sample()
result=dict(before=a,after=b,log=str(log),runtime=str(directory),
            csv=next(directory.glob('frames-*.csv')).read_text())
if audio:
    sinks=subprocess.run(['pactl','list','short','sinks'],capture_output=True,text=True,check=True).stdout
    streams=subprocess.run(['pactl','list','sink-inputs'],capture_output=True,text=True,check=True).stdout
    # Explicit speaker output monitor, never the microphone/default input.
    monitor='alsa_output.1.stereo-fallback.monitor'
    assert 'alsa_output.1.stereo-fallback' in sinks
    capture=subprocess.run(['timeout','3','parec','--device='+monitor,'--raw',
                            '--format=s16le','--rate=22050','--channels=2'],capture_output=True)
    samples=array.array('h',capture.stdout)
    result['audio']=dict(source=monitor,bytes=len(capture.stdout),
        peak=max((abs(v) for v in samples),default=0),
        rms=math.sqrt(sum(v*v for v in samples)/max(1,len(samples))),
        sinks=sinks,streams=streams,physical_audibility_verified=False)
print(json.dumps(result))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("RGDSPLUS_SSH_HOST"))
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--audio", action="store_true")
    args = parser.parse_args()
    assert 5 <= args.seconds <= 300
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(args.host, username="root",
                       password=os.environ["RGDSPLUS_SSH_PASSWORD"],
                       timeout=12, look_for_keys=False, allow_agent=False)
        code = f"seconds={args.seconds}\naudio={args.audio!r}\n" + REMOTE
        _, out, err = client.exec_command("python3 -c " + shlex.quote(code), timeout=args.seconds+30)
        text, errors = out.read().decode(), err.read().decode()
        if out.channel.recv_exit_status():
            raise RuntimeError(errors)
        result = json.loads(text)
        a, b = result["before"], result["after"]
        av = dict(line.split() for line in a["vm"].splitlines())
        bv = dict(line.split() for line in b["vm"].splitlines())
        result["reclaim_delta"] = {k: int(bv.get(k,0))-int(av.get(k,0)) for k in
            ("pgmajfault", "pgscan_kswapd", "pgscan_direct", "pgsteal_kswapd",
             "allocstall_normal", "pgpgin", "pgpgout")}
        result["frames"] = summarize(list(csv.DictReader(io.StringIO(result["csv"]))),
                                     a["t"]*1000, b["t"]*1000)
        destination = ROOT / "validation/r4-review" / f"runtime-sample-{time.time_ns()}.json"
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(dict(frames=result["frames"], reclaim=result["reclaim_delta"],
            memory=b["mem"][:380], audio=result.get("audio")), indent=2))
        print(destination)
    finally:
        client.close()


if __name__ == "__main__":
    main()
