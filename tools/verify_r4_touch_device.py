"""Finite evdev-injection checks on the disposable review clone, never physical acceptance."""

import json
import os
from pathlib import Path
import shlex
import time
import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r'''
import fcntl, json, os, struct, sys, time
from pathlib import Path
import xml.etree.ElementTree as ET
app = Path('/mnt/sdcard/Ports/SlayTheSpireDualR4Review')
sys.path.insert(0, str(app))
from supervisor import identity
from rgds_exit import game_identity
owned = json.loads((app/'logs/recovery.json').read_text())
assert identity(owned['owner']) == owned['birth']
log = Path((app/'logs/latest-path.txt').read_text().strip())
assert log.parent == app/'logs' and game_identity(Path(str(log)[:-4]))
directory = Path(owned['runtime'])
status = json.loads((directory/'touch-state.json').read_text())
assert status['policy'] == 'native-lower-pointer' and status['focused']
assert status['connected'] and all(d['grabbed'] and not d['contacts'] for d in status['devices'])
def screen():
    return {e.attrib['key']: e.text for e in ET.fromstring((directory/'state.xml').read_bytes()).findall('entry')}.get('menu.screen')
def wait_screen(expected):
    until = time.monotonic() + 8
    while time.monotonic() < until:
        if screen() == expected: return
        time.sleep(.2)
    raise AssertionError((expected, screen()))
assert screen() == 'MAIN_MENU', 'Start review at main menu'
def find(name):
    return next('/dev/input/'+p.parents[1].name for p in Path('/sys/class/input').glob('event*/device/name')
                if p.read_text().strip() == name)
fd = os.open(find('gt9xx-0'), os.O_RDWR)
pad = os.open(find('ANBERNIC-rk3568-keys'), os.O_RDWR)
slots = bytearray(24); fcntl.ioctl(fd, 0x80184540+47, slots)
count = struct.unpack('=6i', slots)[2] + 1
ids = bytearray(struct.pack('='+str(count+1)+'i', 57, *([-1]*count)))
fcntl.ioctl(fd, 0x8000450A | (len(ids)<<16), ids)
assert all(v < 0 for v in struct.unpack('='+str(count+1)+'i', ids)[1:])
def report(events, target=fd):
    os.write(target, b''.join(struct.pack('@llHHi',0,0,*e) for e in events+[(0,0,0)]))
def down(x, y):
    report([(3,47,0),(3,57,29001),(3,53,x),(3,54,y),(1,330,1)])
    time.sleep(.18)
def up():
    report([(3,47,0),(3,57,-1),(1,330,0)])
    time.sleep(.18)
def tap(x, y):
    down(x,y); up()
checks = []
try:
    for repeat in range(3):
        tap(190,532); wait_screen('PANEL_MENU')
        tap(270,330); wait_screen('SETTINGS')
        tap(95,667); wait_screen('PANEL_MENU')
        tap(95,667); wait_screen('MAIN_MENU')
    checks.append('three same-location menu/settings/return cycles')
    down(190,532)
    report([(3,47,1),(3,57,29002),(3,53,750),(3,54,500)])
    time.sleep(.18)
    report([(3,47,1),(3,57,-1)])
    up()
    time.sleep(2.5); assert screen() == 'MAIN_MENU'
    checks.append('second finger cancels pending click')
    down(190,532)
    report([(1,305,1)],pad); time.sleep(.15)
    report([(1,305,0)],pad); up()
    time.sleep(2.5); assert screen() == 'MAIN_MENU'
    checks.append('B takeover cancels old touch release')
    tap(190,532); wait_screen('PANEL_MENU')
    report([(1,305,1)],pad); time.sleep(.15); report([(1,305,0)],pad)
    wait_screen('MAIN_MENU')
    checks.append('gamepad B still works after touch')
finally:
    report([(3,47,1),(3,57,-1),(3,47,0),(3,57,-1),(1,330,0)])
    report([(1,305,0)],pad)
    os.close(fd); os.close(pad)
print(json.dumps(dict(source='evdev-injection', physical_verified=False,
    checks=checks, screen=screen(), touch=json.loads((directory/'touch-state.json').read_text()))))
'''


def main():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(os.environ["RGDSPLUS_SSH_HOST"], username="root",
                       password=os.environ["RGDSPLUS_SSH_PASSWORD"],
                       timeout=12, look_for_keys=False, allow_agent=False)
        _, out, err = client.exec_command("python3 -c " + shlex.quote(REMOTE), timeout=100)
        text, errors = out.read().decode(), err.read().decode()
        code = out.channel.recv_exit_status()
        destination = ROOT / "validation/r4-review" / f"touch-check-{time.time_ns()}.json"
        destination.write_text(json.dumps(dict(output=text, errors=errors, exit_code=code,
                                              physical_verified=False), indent=2), encoding="utf-8")
        print(text, errors, destination)
        if code:
            raise RuntimeError("Native touch check failed")
    finally:
        client.close()


if __name__ == "__main__":
    main()
