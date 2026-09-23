"""Bounded native UI interaction checks, only in the disposable R4 review clone."""

import argparse
import json
import os
from pathlib import Path
import shlex
import time
import xml.etree.ElementTree as ET

import paramiko

ROOT = Path(__file__).resolve().parents[1]
APP = "/mnt/sdcard/Ports/SlayTheSpireDualR4Review"
KEYS = {"a": (1, 304, 1), "b": (1, 305, 1), "x": (1, 307, 1),
        "y": (1, 306, 1), "l": (1, 308, 1), "r": (1, 309, 1),
        "start": (1, 311, 1), "l2": (1, 314, 1), "r2": (1, 315, 1),
        "up": (3, 17, -1), "down": (3, 17, 1),
        "left": (3, 16, -1), "right": (3, 16, 1)}


class ReviewDevice:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(os.environ["RGDSPLUS_SSH_HOST"], username="root",
                            password=os.environ["RGDSPLUS_SSH_PASSWORD"], timeout=12,
                            look_for_keys=False, allow_agent=False)
        self.sftp = self.client.open_sftp()
        self.runtime = json.loads(self.read(APP + "/logs/recovery.json"))["runtime"]
        assert self.runtime.startswith("/tmp/rgds-sts-r3-")
        self.checks = []
        self.commands = []

    def read(self, path):
        with self.sftp.open(path, "rb") as stream:
            return stream.read()

    def state(self):
        result = {}
        for name in ("state.xml", "dual-state.xml"):
            root = ET.fromstring(self.read(self.runtime + "/" + name))
            result.update({e.attrib["key"]: e.text or "" for e in root.findall("entry")})
        return result

    def wait(self, predicate, timeout=18):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            state = self.state()
            if predicate(state):
                return state
            time.sleep(.25)
        raise AssertionError(json.dumps(self.state(), ensure_ascii=False))

    def fresh(self):
        frame = self.state()["frames"]
        return self.wait(lambda s: s["frames"] != frame)

    def scene(self, name):
        assert name in {f"u{i:02}" for i in range(1, 34)}
        request = self.runtime + "/page.request"
        result_path = self.runtime + "/page-result.txt"
        try:
            self.sftp.remove(result_path)
        except FileNotFoundError:
            pass
        frame = self.state()["frames"]
        with self.sftp.open(request + ".tmp", "w") as stream:
            stream.write(name)
        self.sftp.posix_rename(request + ".tmp", request)
        self.commands.append({"scene": name, "source": "isolated-native-ui-specimen"})
        until = time.monotonic() + 20
        while True:
            try:
                result = self.read(result_path).decode()
                break
            except FileNotFoundError:
                # The RAM diagnostic session may archive page-result.txt while
                # a heavyweight native page is still settling. ReviewProbe
                # assigns reviewScene only after the page open completed, so
                # that state is a valid fallback for this disposable fixture.
                try:
                    if self.state().get("reviewScene") == name:
                        result = (name + "\nopened\n"
                                  "source=isolated-native-ui-specimen\n"
                                  "physical_verified=false\n")
                        break
                except (FileNotFoundError, ET.ParseError):
                    pass
                if time.monotonic() >= until:
                    raise TimeoutError("Review scene request was not processed")
                time.sleep(.25)
        assert "\nopened\n" in result, result
        self.wait(lambda s: s["reviewScene"] == name and s["frames"] != frame)
        time.sleep(.4)

    def inject(self, actions):
        # An action batch is finite and releases every injected contact/key even
        # if an assertion fails. Real contacts/held physical buttons abort it.
        script = r'''
import fcntl, json, os, struct, sys, time
from pathlib import Path
app = Path('/mnt/sdcard/Ports/SlayTheSpireDualR4Review')
sys.path.insert(0, str(app))
from supervisor import identity
from rgds_exit import game_identity
owned = json.loads((app/'logs/recovery.json').read_text())
assert identity(owned['owner']) == owned['birth']
log = Path((app/'logs/latest-path.txt').read_text().strip())
assert log.parent == app/'logs' and game_identity(Path(str(log)[:-4]))
status = json.loads((Path(owned['runtime'])/'touch-state.json').read_text())
assert status['policy'] == 'native-lower-pointer' and status['focused']
assert status['connected'] and all(d['grabbed'] and not d['contacts'] for d in status['devices'])
def device(name):
    return next('/dev/input/'+p.parents[1].name for p in Path('/sys/class/input').glob('event*/device/name')
                if p.read_text().strip() == name)
fd = os.open(device('gt9xx-0'), os.O_RDWR)
pad = os.open(device('ANBERNIC-rk3568-keys'), os.O_RDWR)
bits = bytearray(96); fcntl.ioctl(pad, 0x80604518, bits)
assert not any(bits), 'Physical controller held'
slots = bytearray(24); fcntl.ioctl(fd, 0x80184540+47, slots)
count = struct.unpack('=6i', slots)[2] + 1
ids = bytearray(struct.pack('='+str(count+1)+'i', 57, *([-1]*count)))
fcntl.ioctl(fd, 0x8000450A | (len(ids)<<16), ids)
assert all(v < 0 for v in struct.unpack('='+str(count+1)+'i', ids)[1:]), 'Physical touch active'
def report(events, target=fd):
    os.write(target, b''.join(struct.pack('@llHHi',0,0,*e) for e in events+[(0,0,0)]))
try:
    for action in ACTIONS:
        kind = action[0]
        if kind == 'tap':
            x,y=action[1:]
            report([(3,47,0),(3,57,31001),(3,53,x),(3,54,y),(1,330,1)])
            time.sleep(.16)
            report([(3,47,0),(3,57,-1),(1,330,0)])
        elif kind == 'key':
            event = action[1:]
            report([event], pad); time.sleep(.15)
            report([(event[0],event[1],0)], pad)
        elif kind == 'cancel-touch':
            x,y=action[1:]
            report([(3,47,0),(3,57,31001),(3,53,x),(3,54,y),(1,330,1)])
            time.sleep(.16)
            report([(1,305,1)],pad); time.sleep(.15)
            report([(1,305,0)],pad)
            report([(3,47,0),(3,57,-1),(1,330,0)])
        elif kind == 'multi':
            x,y=action[1:]
            report([(3,47,0),(3,57,31001),(3,53,x),(3,54,y),(1,330,1)])
            time.sleep(.16)
            report([(3,47,1),(3,57,31002),(3,53,800),(3,54,500)])
            time.sleep(.16)
            report([(3,47,1),(3,57,-1),(3,47,0),(3,57,-1),(1,330,0)])
        elif kind == 'release-outside':
            x,y,end_x,end_y=action[1:]
            report([(3,47,0),(3,57,31001),(3,53,x),(3,54,y),(1,330,1)])
            time.sleep(.16)
            report([(3,47,0),(3,53,end_x),(3,54,end_y),(3,57,-1),(1,330,0)])
        time.sleep(.45)
finally:
    report([(3,47,1),(3,57,-1),(3,47,0),(3,57,-1),(1,330,0)])
    for kind,code,value in PAD_KEYS: report([(kind,code,0)],pad)
    os.close(fd); os.close(pad)
'''.replace("ACTIONS", repr(actions)).replace("PAD_KEYS", repr(list(KEYS.values())))
        _, stdout, stderr = self.client.exec_command("python3 -c " + shlex.quote(script), timeout=60)
        output, errors = stdout.read().decode(), stderr.read().decode()
        assert stdout.channel.recv_exit_status() == 0, output + errors
        self.commands.append({"actions": actions, "source": "evdev-injection"})

    def key(self, *keys):
        self.inject([("key", *KEYS[key]) for key in keys])

    def tap(self, x, y):
        self.inject([("tap", round(x), round(y))])

    def hit(self, name):
        state = self.fresh()
        # Diagnostics are periodic and card entry/hover animations can outlive
        # the first snapshot. Require two current positions to agree.
        until = time.monotonic() + 20
        while time.monotonic() < until:
            next_state = self.fresh()
            keys = ["ui." + name + "." + axis for axis in ("x", "y")]
            if all(key in state and key in next_state and
                   abs(float(state[key]) - float(next_state[key])) < 2 for key in keys):
                state = next_state
                break
            state = next_state
        else:
            raise AssertionError("Hitbox did not settle: " + name)
        self.tap(float(state["ui." + name + ".x"]), float(state["ui." + name + ".y"]))

    def passed(self, name, before=None):
        after = self.fresh()
        self.checks.append({"check": name, "before": before, "after": after})
        print("PASS", name, flush=True)
        return after


def keyboard(device):
    for page, hit in (("u04", "seed"), ("u05", "customSeed")):
        device.scene(page)
        device.hit(hit)
        device.wait(lambda s: s.get("keyboard.open") == "true")
        device.tap(880, 563)  # Clear
        device.inject([("tap", 85, 259), ("tap", 179, 259), ("tap", 273, 259)])
        device.wait(lambda s: s.get("keyboard.text") == "123")
        device.key("x")  # Backspace, never type the physical key's letter.
        device.wait(lambda s: s.get("keyboard.text") == "12")
        device.inject([("multi", 85, 259)])
        assert device.fresh().get("keyboard.text") == "12"
        device.tap(750, 639)
        device.wait(lambda s: s.get("keyboard.open") == "false" and s.get("ui.seed") == "12")
        device.hit(hit)
        device.wait(lambda s: s.get("keyboard.open") == "true")
        device.tap(85, 259)
        device.inject([("cancel-touch", 179, 259)])
        device.wait(lambda s: s.get("keyboard.open") == "false")
        assert device.fresh().get("ui.seed") == "12"
        device.passed(page + " seed edit/clear/backspace/confirm/multifinger/B-cancel")


def names(device):
    device.scene("u03")
    before = device.state()
    assert before["ui.slot.0.empty"] == "false", "Use existing review slot only"
    device.hit("rename.0")
    device.wait(lambda s: s.get("keyboard.kind") == "name")
    device.tap(880, 563)
    # abc, space, a digit, hyphen; native confirmation persists only review prefs.
    device.inject([("tap", 85, 411), ("tap", 461, 487), ("tap", 273, 487),
                   ("tap", 410, 563), ("tap", 85, 259), ("tap", 931, 411)])
    device.wait(lambda s: s.get("keyboard.text") == "abc 1-")
    device.key("y")
    device.wait(lambda s: s.get("keyboard.open") == "false" and s.get("ui.slot.0.name") == "abc 1-")
    device.hit("rename.0")
    device.wait(lambda s: s.get("keyboard.open") == "true")
    device.key("right", "a")
    device.wait(lambda s: s.get("keyboard.text") == "abc 1-2")
    device.inject([("cancel-touch", 179, 259)])
    device.wait(lambda s: s.get("keyboard.open") == "false")
    assert device.state()["ui.slot.0.name"] == "abc 1-"
    device.passed("review rename, space/punctuation, pad typing/Y confirm and B cancel", before)


def potions(device):
    device.scene("u12")
    before = device.state()
    device.key("b")
    device.wait(lambda s: s.get("ui.potion.hidden") == "true")
    assert device.state()["ui.potion.0.id"] == before["ui.potion.0.id"]
    device.key("x", "a", "a")
    device.wait(lambda s: s.get("ui.potion.target") == "true")
    device.key("b")
    device.wait(lambda s: s.get("ui.potion.target") == "false")
    device.passed("potion native pad targeting then B does not consume", before)
    device.key("x", "a", "a")
    device.wait(lambda s: s.get("ui.potion.target") == "true")
    device.tap(512, 397)
    device.wait(lambda s: s.get("ui.potion.target") == "false")
    after = device.state()
    for key in ("energy.totalCount", "hand.count", "ui.potion.0.id", "monsters.0.currentHealth"):
        assert before[key] == after[key], key
    device.passed("lower touch cancels potion target without card or potion use", before)
    device.key("x", "a", "down", "a")
    device.wait(lambda s: s.get("ui.potion.0.id") == "Potion Slot")
    device.passed("potion native discard")


def details(device):
    device.scene("u25")
    before = device.state()
    device.tap(512, 360)
    assert device.fresh().get("ui.cardPopup") == "true"
    device.hit("detailClose")
    device.wait(lambda s: s.get("ui.cardPopup") == "false")
    after = device.state()
    for key in ("energy.totalCount", "hand.count", "ui.masterDeck.count"):
        assert before[key] == after[key], key
    device.passed("detail lower close; blank area and old release do not affect parent", before)


def rewards(device):
    device.scene("u18")
    before = device.state()
    device.hit("cards.0")
    after = device.fresh()
    assert after["ui.masterDeck.count"] == before["ui.masterDeck.count"]
    device.hit("confirm")
    device.wait(lambda s: int(s["ui.masterDeck.count"]) == int(before["ui.masterDeck.count"]) + 1)
    device.passed("card reward touch preview then native single confirmation", before)
    device.scene("u17")
    before = device.state()
    device.hit("rewards.0")
    after = device.fresh()
    if after["player.gold"] == before["player.gold"]:
        device.hit("rewards.0")
    device.wait(lambda s: int(s["player.gold"]) == int(before["player.gold"]) + 25)
    device.passed("native gold reward changes gold once", before)


def events(device):
    device.scene("u21")
    before = device.fresh()
    x, y = (round(float(before["ui.eventOptions.1." + axis])) for axis in ("x", "y"))
    for action in (("release-outside", x, y, 40, 700),
                   ("multi", x, y), ("cancel-touch", x, y)):
        device.inject([action])
        after = device.fresh()
        assert after["ui.eventOptions.count"] == "3"
        assert after["player.maxHealth"] == before["player.maxHealth"]
    device.hit("eventOptions.1")
    device.wait(lambda s: s.get("ui.eventOptions.count") == "1" and
                int(s["player.maxHealth"]) == int(before["player.maxHealth"]) + 5)
    device.passed("event lower touch commits once; outside/multifinger/B releases cancel", before)
    device.hit("eventOptions.0")
    device.wait(lambda s: s.get("dungeon.screen") == "MAP")
    device.passed("event leave touch opens native map")


def tutorial(device):
    before = device.wait(lambda s: s.get("ui.tutorial.slot") == "0", timeout=120)
    for slot in ("-1", "-2"):
        device.hit("proceed")
        device.wait(lambda s: s.get("dungeon.screen") == "FTUE" and
                    s.get("ui.tutorial.slot") == slot)
        device.passed("tutorial touch page " + slot + " stays in FTUE")
    device.hit("proceed")
    device.wait(lambda s: s.get("dungeon.screen") == "NONE" and int(s["hand.count"]) > 0)
    after = device.fresh()
    assert after.get("touch.hand.0.hovered") == "false"
    assert float(after["touch.hand.0.targetAngle"]) != 0
    assert after["player.isDraggingCard"] == "false"
    device.passed("tutorial touch completion enters combat with neutral fan hand", before)


def information(device):
    device.scene("u08")
    before = device.state()
    device.key("up")
    first = device.wait(lambda s: s.get("ui.inspect") == "true")
    device.key("right")
    device.wait(lambda s: s.get("ui.inspect.x") != first.get("ui.inspect.x"))
    device.key("down", "x", "down")
    device.wait(lambda s: s.get("ui.viewingRelics") == "true")
    device.key("a")
    device.wait(lambda s: s.get("ui.relicPopup") == "true")
    device.key("b")
    device.wait(lambda s: s.get("ui.relicPopup") == "false")
    after = device.state()
    for key in ("energy.totalCount", "hand.count", "ui.masterDeck.count"):
        assert before[key] == after[key], key
    device.passed("native status/enemy inspect, relic detail and B return", before)
    device.key("b")


def selections(device):
    device.scene("u14")
    device.hit("handCards.0")
    device.wait(lambda s: s.get("ui.hand.selected") == "1")
    device.hit("handConfirm")
    device.wait(lambda s: s.get("dungeon.screen") == "NONE")
    device.passed("native hand selection and confirmation")
    device.scene("u15")
    device.hit("gridCards.0")
    device.wait(lambda s: s.get("ui.grid.confirm") == "true")
    device.key("b")
    device.wait(lambda s: s.get("ui.grid.confirm") == "false")
    device.hit("gridCards.0")
    device.wait(lambda s: s.get("ui.grid.confirm") == "true")
    device.hit("gridConfirm")
    device.wait(lambda s: s.get("ui.grid.selected") == "1")
    device.passed("native upgrade selection, preview cancel, selection confirm (fixture, no upgrade action)")
    device.scene("u16")
    before = device.state()
    device.hit("cards.0")
    device.fresh()
    device.hit("confirm")
    device.wait(lambda s: s.get("dungeon.screen") == "NONE")
    assert device.state()["ui.masterDeck.count"] == before["ui.masterDeck.count"]
    device.passed("temporary choose-one returns without adding to permanent deck", before)


def pages(device):
    for page, screen in (("u26", "SETTINGS"), ("u29", "CARD_LIBRARY"),
                         ("u30", "STATS"), ("u31", "CREDITS"), ("u32", "LEADERBOARD")):
        device.scene(page)
        before = device.state()
        device.key("b")
        device.wait(lambda s: s.get("menu.screen") != screen and s.get("dungeon.screen") != screen)
        device.passed(page + " native B return", before)
    device.scene("u27")
    device.key("b")
    device.wait(lambda s: s.get("menu.screen") == "MAIN_MENU")
    device.passed("abandon confirmation cancels without ending run")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("keyboard", "names", "potions", "details", "rewards",
                                           "information", "selections", "pages", "events", "tutorial"), required=True)
    args = parser.parse_args()
    device = ReviewDevice()
    evidence = dict(case=args.case, source="evdev-injection-on-isolated-native-fixtures",
                    physical_verified=False, natural_flow_verified=False)
    try:
        globals()[args.case](device)
        evidence["passed"] = True
    except Exception as error:
        evidence["passed"] = False
        evidence["error"] = str(error)
        raise
    finally:
        evidence["commands"], evidence["checks"] = device.commands, device.checks
        try:
            evidence["final_state"] = device.state()
        except Exception as error:
            evidence["final_state_error"] = str(error)
        finally:
            device.client.close()
        path = ROOT / "validation/r4-review" / f"interfaces-{args.case}-{time.time_ns()}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(path, flush=True)


if __name__ == "__main__":
    main()
