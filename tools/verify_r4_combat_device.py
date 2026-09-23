"""Bounded evdev combat regressions on the disposable review clone only."""

import argparse
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
def xml(name):
    return {e.attrib['key']: e.text for e in ET.fromstring((directory/name).read_bytes()).findall('entry')}
def state():
    return xml('state.xml')
def wait_for(predicate, timeout=10):
    until = time.monotonic()+timeout
    while time.monotonic() < until:
        value = state()
        if predicate(value): return value
        time.sleep(.1)
    raise AssertionError(('state timeout', state()))
def wait_dual(predicate, timeout=12):
    frame = xml('dual-state.xml')['frames']
    until = time.monotonic()+timeout
    while time.monotonic() < until:
        value = xml('dual-state.xml')
        if value['frames'] != frame and predicate(value): return value
        time.sleep(.1)
    raise AssertionError(('dual state timeout', xml('dual-state.xml')))
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
def down(x,y):
    report([(3,47,0),(3,57,29501),(3,53,x),(3,54,y),(1,330,1)]); time.sleep(.2)
def move(x,y):
    report([(3,47,0),(3,53,x),(3,54,y)])
def up():
    report([(3,47,0),(3,57,-1),(1,330,0)])
def b():
    report([(1,305,1)],pad); time.sleep(.12); report([(1,305,0)],pad)
def capture_frame():
    capture=directory/'capture.pam'
    if capture.exists(): capture.unlink()
    (directory/'capture.request').write_text('capture\n')
    until=time.monotonic()+10
    while time.monotonic()<until:
        if capture.exists() and capture.stat().st_size >= 2048*768*4:
            return True
        time.sleep(.01)
    raise AssertionError('No framebuffer capture')
def metrics(value):
    return {k:v for k,v in value.items() if k.startswith(
        ('hand.','energy.','drawPile.','discardPile.','exhaustPile.','player.current','monsters.'))}
time.sleep(5.2)
before, dual = state(), xml('dual-state.xml')
assert before['room.phase'] == 'COMBAT' and before['dungeon.screen'] == 'NONE'
result = dict(action=action, source='evdev-injection', physical_verified=False, before=before,
              started_ms=time.monotonic()*1000, runtime=str(directory), capture=False)
try:
    if flight_delay is not None:
        assert action in ('strike','high','defend','rearm')
        (directory/'capture.request').unlink(missing_ok=True)
        time.sleep(.35)
        result['capture_kind']='normal-animation-after-release'
        result['capture_delay']=flight_delay
    if action == 'hand-entry':
        assert int(before['hand.count']) >= 3
        assert not before.get('hoveredCard.cardID'), 'Entry must not auto-select the first card'
        assert all(dual.get(f'touch.hand.{i}.hovered') == 'false'
                   for i in range(int(before['hand.count'])))
        assert abs(float(dual['touch.hand.0.angle'])) > 1, 'First card must follow the fan angle'
        assert abs(float(dual['touch.hand.0.angle']) -
                   float(dual['touch.hand.0.targetAngle'])) < .1
        assert float(dual['touch.hand.0.y']) > float(dual['touch.hand.2.y']), 'First card is lifted'
        result['entry']=dual
        result['capture']=capture_frame()
        report([(3,16,1)],pad); time.sleep(.12); report([(3,16,0)],pad)
        selected=wait_for(lambda s: bool(s.get('hoveredCard.cardID')))
        assert metrics(selected)==metrics(before), 'Pad selection must not play a card'
        result['pad_selected']=selected
        down(68,706); up()
        opened=wait_for(lambda s: s.get('dungeon.screen')=='GAME_DECK_VIEW')
        assert metrics(opened)==metrics(before), 'Touch after pad must not play the old selection'
        result['opened']=opened
        b(); wait_for(lambda s: s.get('dungeon.screen')=='NONE')
    elif action == 'end-turn':
        assert before['energy.totalCount']=='0', 'Run after consuming this turn energy'
        down(875,618); up()
        after=wait_for(lambda s: s.get('energy.totalCount')=='3' and s.get('hand.count')=='5',20)
        assert int(after['player.currentHealth']) < int(before['player.currentHealth'])
    elif action == 'pile':
        down(68,706); up()
        opened=wait_for(lambda s: s.get('dungeon.screen') == 'GAME_DECK_VIEW')
        assert metrics(opened) == metrics(before), 'Pile click mutated combat'
        result['opened']=opened
        b(); wait_for(lambda s: s.get('dungeon.screen') == 'NONE')
    else:
        card_id='Defend_R' if action in ('defend','self-cancel') else 'Strike_R'
        index=next(i for i in range(int(before['hand.count'])) if before[f'hand.{i}.cardID']==card_id)
        x,y=round(float(dual[f'touch.hand.{index}.x'])),round(float(dual[f'touch.hand.{index}.y']))
        mx,my=float(dual['touch.monster.0.x']),float(dual['touch.monster.0.y'])
        dest_y=70 if action=='high' else max(20,y-28)
        dest_x=x
        result['path']=[(x,y),(dest_x,dest_y)]
        down(x,y)
        for step in range(1,13):
            move(round(x+(dest_x-x)*step/12),round(y+(dest_y-y)*step/12)); time.sleep(.025)
        time.sleep(.5)
        aimed=wait_for(lambda s: s.get('player.isDraggingCard' if card_id=='Defend_R' else 'player.inSingleTargetMode')=='true')
        result['aimed']=aimed
        locked=wait_dual(lambda s: s.get('touch.armed')=='true')
        result['locked']=locked
        target_index=int(locked['touch.targetIndex'])
        if action=='sticky':
            assert target_index >= 0
            for height in (max(3,y-150),70,3,max(3,y-10)):
                move(x,height)
                sample=wait_dual(lambda s: s.get('touch.cardY') is not None)
                assert sample['touch.targetIndex']==str(target_index) and sample['touch.armed']=='true'
                result.setdefault('vertical_samples',[]).append(sample)
            move(x,y+10)
            returned=wait_dual(lambda s: s.get('touch.armed')=='false')
            assert returned.get('touch.card')==card_id and returned['touch.targetIndex']=='-1'
            result['returned']=returned
            move(x,70)
            result['rearmed']=wait_dual(lambda s: s.get('touch.armed')=='true')
            assert result['rearmed']['touch.targetIndex']==str(target_index)
        if action=='switch':
            assert sum(before.get(f'monsters.{i}.isDead')=='false' for i in range(int(before['monsters.count'])))>=2
            current=float(dual[f'touch.monster.{target_index}.x'])
            others=[float(dual[f'touch.monster.{i}.x']) for i in range(int(before['monsters.count']))
                    if i != target_index and before.get(f'monsters.{i}.isDead')=='false']
            direction=1 if any(v>current for v in others) else -1
            sx=x+direction*68
            assert 3<sx<1021, 'Choose a card with room for horizontal switch'
            move(sx,dest_y)
            switched=wait_dual(lambda s: s.get('touch.targetIndex') not in ('-1',str(target_index)))
            result['switched']=switched
            move(sx,3)
            high=wait_dual(lambda s: s.get('touch.armed')=='true')
            assert high['touch.targetIndex']==switched['touch.targetIndex']
            result['switched_high']=high
            move(x,70)
            result['switched_back']=wait_dual(lambda s: s.get('touch.targetIndex')==str(target_index))
        if action=='rearm':
            move(x,y+10)
            returned=wait_dual(lambda s: s.get('touch.armed')=='false')
            assert returned.get('touch.card')==card_id
            move(x,y-28)
            result['rearmed']=wait_dual(lambda s: s.get('touch.armed')=='true')
            target_index=int(result['rearmed']['touch.targetIndex'])
        if flight_delay is None and action in ('strike','high','defend','sticky','switch','self-cancel','rearm'):
            result['capture']=capture_frame()
        if action=='cancel-b': b()
        if action=='cancel-second':
            report([(3,47,1),(3,57,29502),(3,53,800),(3,54,500)])
            time.sleep(.2); report([(3,47,1),(3,57,-1)])
        if action=='drag-back': move(x,y); time.sleep(.2)
        if action=='edge': move(dest_x,1); time.sleep(.2)
        if action in ('sticky','switch','self-cancel'): b()
        if action=='final-return':
            report([(3,47,0),(3,53,x),(3,54,y),(3,57,-1),(1,330,0)])
            time.sleep(.1)
        up()
        if flight_delay is not None:
            result['release_ms']=time.monotonic()*1000
            time.sleep(flight_delay)
            result['capture']=capture_frame()
            result['capture_ready_ms']=time.monotonic()*1000
        if action in ('strike','high','defend','rearm'):
            wait_for(lambda s: int(s.get('energy.totalCount',999)) == int(before['energy.totalCount'])-1)
            time.sleep(2)
            after=state()
            assert int(after['hand.count'])==int(before['hand.count'])-1, 'Exactly one card must leave hand'
            assert int(after['discardPile.count'])==int(before['discardPile.count'])+1
            old=sum(int(before.get(f'monsters.{target_index}.'+key,0)) for key in ('currentHealth','currentBlock'))
            new=sum(int(after.get(f'monsters.{target_index}.'+key,0)) for key in ('currentHealth','currentBlock'))
            if action=='defend':
                assert int(after['player.currentBlock'])==int(before['player.currentBlock'])+5
            else:
                assert new < old, 'Native attack must damage the selected enemy'
        else:
            time.sleep(2)
            assert metrics(state())==metrics(before), 'Cancelled gesture mutated combat'
    time.sleep(5.2)
    result.update(after=state(),dual=xml('dual-state.xml'),ended_ms=time.monotonic()*1000)
    expected_commits = 1 if action in ('strike','high','defend','rearm') else 0
    assert int(result['dual']['touch.commits'])-int(dual['touch.commits']) == expected_commits
    if expected_commits:
        assert int(result['dual']['flight.launched'])-int(dual['flight.launched']) == 1
        assert int(result['dual']['flight.lowerFrames']) > int(dual['flight.lowerFrames'])
        assert int(result['dual']['flight.upperFrames']) > int(dual['flight.upperFrames'])
finally:
    report([(3,47,1),(3,57,-1),(3,47,0),(3,57,-1),(1,330,0)])
    report([(1,305,0)],pad)
    report([(3,16,0)],pad)
    os.close(fd); os.close(pad)
print(json.dumps(result))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pile", "strike", "high", "defend", "end-turn", "cancel-b",
                                         "cancel-second", "drag-back", "edge", "sticky", "switch",
                                         "self-cancel", "rearm", "final-return", "hand-entry"))
    parser.add_argument("--flight-delay", type=float)
    args = parser.parse_args()
    if args.flight_delay is not None and (not 0 <= args.flight_delay <= .3 or
            args.action not in ("strike", "high", "defend", "rearm")):
        parser.error("Flight capture requires a card play and a delay from 0 to .3 seconds")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    output = ROOT / "validation/r4-review"
    name = f"combat-{args.action}-{time.time_ns()}"
    try:
        client.connect(os.environ["RGDSPLUS_SSH_HOST"], username="root",
                       password=os.environ["RGDSPLUS_SSH_PASSWORD"],
                       timeout=12, look_for_keys=False, allow_agent=False)
        code = "action=" + repr(args.action) + "\nflight_delay=" + repr(args.flight_delay) + "\n" + REMOTE
        _, out, err = client.exec_command("python3 -c " + shlex.quote(code), timeout=90)
        text, errors = out.read().decode(), err.read().decode()
        exit_code = out.channel.recv_exit_status()
        (output / (name + ".json")).write_text(json.dumps(dict(output=text, errors=errors,
            exit_code=exit_code, physical_verified=False), indent=2), encoding="utf-8")
        if exit_code:
            raise RuntimeError(errors)
        result = json.loads(text)
        if result["capture"]:
            from PIL import Image
            with client.open_sftp() as sftp:
                with sftp.open(result["runtime"] + "/capture.pam", "rb") as stream:
                    header, pixels = stream.read().split(b"ENDHDR\n",1)
                image = Image.frombytes("RGBA", (2048,768), pixels).convert("RGB")
                stacked = Image.new("RGB", (1024,1536))
                stacked.paste(image.crop((0,0,1024,768)),(0,0))
                stacked.paste(image.crop((1024,0,2048,768)),(0,768))
                stacked.save(output/(name+".png"))
                for item in ("capture.pam","capture.request"):
                    sftp.remove(result["runtime"]+"/"+item)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(output/(name+".json"))
    finally:
        client.close()


if __name__ == "__main__":
    main()
