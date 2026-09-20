"""Linux evdev input, with a pure Type-B packet reducer for regression tests."""

import glob
import itertools
import os
from pathlib import Path
import select
import struct

EVENT = struct.Struct("@llHHi")
KEYS = {304: "a", 305: "b", 307: "x", 306: "y",
        308: "l", 309: "r", 314: "l2", 315: "r2"}
EXIT_KEYS = {"ANBERNIC-rk3568-keys": {310, 312}, "adc-keys": {158}}
SOURCES = itertools.count(1)


class Touch:
    def __init__(self, xmax=1024, ymax=768, xmin=0, ymin=0):
        self.bounds = xmin, xmax, ymin, ymax
        self.source = next(SOURCES)
        self.slots = {}
        self.slot = 0
        self.active = None
        self.serial = 0
        self.blocked = False
        self.dropped = False
        self.point = None

    def cancel(self):
        self.active = None
        self.blocked = True
        self.point = None

    def feed(self, kind, code, value):
        if kind == 0 and code == 3:
            self.cancel()
            self.dropped = True
            return [("cancel", "syn-dropped")]
        if self.dropped:
            if kind == 0 and code == 0:
                self.dropped = False
                return [("resync",)]
            return []
        if kind == 3:
            if code == 47:
                self.slot = value
            elif code in (57, 53, 54):
                self.slots.setdefault(self.slot, {})[code] = value
            return []
        if kind != 0 or code != 0:
            return []
        live = [(slot, data) for slot, data in self.slots.items()
                if data.get(57, -1) >= 0]
        if len(live) > 1:
            self.cancel()
            return [("cancel", "second-finger")]
        if self.blocked:
            if not live:
                self.blocked = False
            return []
        if not live:
            if self.active is None:
                return []
            data = self.slots.get(self.active[2], {})
            xmin, xmax, ymin, ymax = self.bounds
            final = ((data.get(53, xmin) - xmin) * 1024 / (xmax - xmin),
                     (data.get(54, ymin) - ymin) * 768 / (ymax - ymin))
            actions = [("move", self.active, *final)] if final != self.point else []
            token, self.active = self.active, None
            self.point = None
            return actions + [("up", token)]
        slot, data = live[0]
        if 53 not in data or 54 not in data:
            self.cancel()
            return [("cancel", "missing-coordinates")]
        xmin, xmax, ymin, ymax = self.bounds
        point = ((data[53] - xmin) * 1024 / (xmax - xmin),
                 (data[54] - ymin) * 768 / (ymax - ymin))
        contact = (slot, data[57])
        if self.active is None:
            self.serial += 1
            self.active = (self.source, self.serial, *contact)
            self.point = point
            return [("down", self.active, *point)]
        if self.active[2:] != contact:
            self.cancel()
            return [("cancel", "contact-replaced")]
        if point != self.point:
            self.point = point
            return [("move", self.active, *point)]
        return []


class Devices:
    def __init__(self, guard=False, emit=lambda event: None):
        import fcntl
        self.ioctl = fcntl.ioctl
        self.guard = guard
        self.devices = {}
        self.holds = {}
        self.next_scan = 0
        self.focused = False
        self.emit = emit
        self.raw_touch_events = 0
        self.touch_reports = 0
        self.touch_actions = 0

    def set_focus(self, focused):
        if focused == self.focused:
            return
        self.focused = focused
        for fd, data in self.devices.items():
            if data["touch"]:
                self.ioctl(fd, 0x40044590, int(focused))
                data["grabbed"] = focused
                self.resync(fd, data["touch"])
                self.emit(dict(event="touch-grab", active=focused, path=data["path"]))

    def diagnostics(self):
        return dict(focused=self.focused, raw_events=self.raw_touch_events,
                    reports=self.touch_reports, actions=self.touch_actions,
                    devices=[dict(path=d["path"], grabbed=d["grabbed"],
                                  blocked=d["touch"].blocked,
                                  contacts=sum(s.get(57, -1) >= 0
                                               for s in d["touch"].slots.values()))
                             for d in self.devices.values() if d["touch"]])

    def resync(self, fd, touch):
        # Drop queued pre-focus/pre-resync packets before querying current state.
        while True:
            try:
                if not os.read(fd, EVENT.size * 256):
                    raise OSError("touch device disconnected during resync")
            except BlockingIOError:
                break
        data = self.devices[fd]
        count = data["slots"]
        slot_info = bytearray(24)
        self.ioctl(fd, 0x80184540 + 47, slot_info)
        touch.slot = struct.unpack("=6i", slot_info)[0]
        touch.slots.clear()
        for code in (57, 53, 54):
            values = bytearray(struct.pack(f"={count + 1}i", code, *([-1] * count)))
            self.ioctl(fd, 0x8000450A | (len(values) << 16), values)
            for slot, value in enumerate(struct.unpack(f"={count + 1}i", values)[1:]):
                touch.slots.setdefault(slot, {})[code] = value
        touch.cancel()
        touch.blocked = any(d.get(57, -1) >= 0 for d in touch.slots.values())

    def scan(self, now):
        self.next_scan = now + 2
        paths = {d["path"] for d in self.devices.values()}
        for namefile in glob.glob("/sys/class/input/event*/device/name"):
            name = Path(namefile).read_text().strip()
            if name not in EXIT_KEYS and (self.guard or name != "gt9xx-0"):
                continue
            path = "/dev/input/" + Path(namefile).parents[1].name
            if path in paths:
                continue
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            data = dict(path=path, name=name, ignored=set(), axes={}, touch=None, grabbed=False)
            self.devices[fd] = data
            try:
                if name == "gt9xx-0":
                    def axis(code):
                        value = bytearray(24)
                        self.ioctl(fd, 0x80184540 + code, value)
                        return struct.unpack("=6i", value)
                    x, y, slots = axis(53), axis(54), axis(47)
                    data["slots"] = min(32, slots[2] + 1)
                    data["touch"] = Touch(x[2], y[2], x[1], y[1])
                    if self.focused:
                        self.ioctl(fd, 0x40044590, 1)
                        data["grabbed"] = True
                    self.resync(fd, data["touch"])
                    print(f"[input] {name} {path} x={x[1:3]} y={y[1:3]}", flush=True)
                else:
                    bits = bytearray(96)
                    self.ioctl(fd, 0x80604518, bits)
                    data["ignored"] = {i for i in range(768)
                                       if bits[i // 8] & (1 << (i % 8))}
                    for code in (16, 17):
                        values = bytearray(24)
                        try:
                            self.ioctl(fd, 0x80184540 + code, values)
                            data["axes"][code] = struct.unpack("=6i", values)[0]
                        except OSError:
                            pass
            except Exception:
                os.close(fd)
                del self.devices[fd]
                raise

    def cancel_touch(self):
        for data in self.devices.values():
            if data["touch"]:
                data["touch"].cancel()

    def poll(self, now):
        if now >= self.next_scan:
            self.scan(now)
        actions = []
        ready, _, _ = select.select(list(self.devices), [], [], 0)
        for fd in ready:
            data = self.devices[fd]
            try:
                raw = os.read(fd, EVENT.size * 256)
                if not raw:
                    raise OSError("input disconnected")
            except OSError:
                os.close(fd)
                del self.devices[fd]
                self.holds = {k: v for k, v in self.holds.items() if k[0] != fd}
                actions.append(("cancel", "disconnect"))
                continue
            for _, _, kind, code, value in EVENT.iter_unpack(raw):
                if data["touch"]:
                    self.raw_touch_events += 1
                    if kind == 0 and code == 0:
                        self.touch_reports += 1
                    # Bounded raw evidence distinguishes real missing events from filtering.
                    if self.raw_touch_events <= 128:
                        self.emit(dict(event="touch-raw", kind=kind, code=code, value=value))
                    events = data["touch"].feed(kind, code, value)
                    if ("resync",) in events:
                        self.resync(fd, data["touch"])
                        break
                    else:
                        actions.extend(events)
                        self.touch_actions += len(events)
                    continue
                if kind == 0 and code == 3:
                    self.holds = {k: v for k, v in self.holds.items() if k[0] != fd}
                    # Drain the stream and reopen with kernel key/axis state.
                    os.close(fd)
                    del self.devices[fd]
                    actions.append(("cancel", "syn-dropped"))
                    break
                if kind == 1:
                    if value == 0:
                        data["ignored"].discard(code)
                        self.holds.pop((fd, code), None)
                    if code in data["ignored"]:
                        continue
                    if code in EXIT_KEYS.get(data["name"], set()) and value == 1:
                        self.holds.setdefault((fd, code), now)
                    if value == 1 and code in KEYS and not self.guard:
                        actions.append(("button", KEYS[code]))
                if kind == 3 and code in (16, 17):
                    old = data["axes"].get(code, 0)
                    data["axes"][code] = value
                    if value and not old and code == 16 and not self.guard:
                        actions.append(("button", "left" if value < 0 else "right"))
        return actions

    def exit_held(self, now):
        return any(now - since >= 1.5 for since in self.holds.values())

    def close(self):
        for fd in self.devices:
            os.close(fd)
        self.devices.clear()


def dispatch(model, actions):
    # Cancellation wins a batch, regardless of kernel fd enumeration order.
    cancels = [a for a in actions if a[0] == "cancel" or a == ("button", "b")]
    if cancels:
        reason = cancels[0][1] if cancels[0][0] == "cancel" else "cancelled"
        model.cancel(reason)
        return
    for action in actions:
        getattr(model, action[0])(*action[1:])
