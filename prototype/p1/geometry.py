"""Game-free P1 geometry and input ownership. No display or device dependencies."""

from dataclasses import dataclass
import math

W, H = 1024, 768
CARD_X = (160, 512, 864)
CARD_IDS = ("C1", "C2", "C3")
CARD_Y = 590
SCENES = ("single", "pair", "five", "overlap", "flanking")
AIM_UP = 48
OUTER_SNAP = 0.14
SWITCH_MARGIN = 0.035


@dataclass(frozen=True)
class Target:
    uid: str
    x: float
    y: float
    w: float = 88
    h: float = 128


def scene_targets(index, generation):
    points = (
        [(512, 350)],
        [(300, 350), (724, 350)],
        [(120, 350), (316, 350), (512, 350), (708, 350), (904, 350)],
        [(492, 350), (532, 350)],
        [(80, 500), (512, 260), (944, 500)],
    )[index]
    return [Target(f"{generation}:{i + 1}", x, y) for i, (x, y) in enumerate(points)]


def angular_interval(origin, target):
    ox, oy = origin
    angles = [math.atan2(x - ox, oy - y)
              for x in (target.x - target.w / 2, target.x + target.w / 2)
              for y in (target.y - target.h / 2, target.y + target.h / 2)]
    return min(angles), max(angles)


def pick(origin, pointer, targets, previous=None):
    dx, up = pointer[0] - origin[0], origin[1] - pointer[1]
    if up < AIM_UP:
        return None, "ready"
    angle = math.atan2(dx, up)
    candidates = []
    for target in targets:
        lo, hi = angular_interval(origin, target)
        distance = max(lo - angle, angle - hi, 0)
        center = math.atan2(target.x - origin[0], origin[1] - target.y)
        candidates.append((target.uid, distance, abs(angle - center)))
    # Overlapping angular hitboxes must never resolve by array order.
    direct = [uid for uid, distance, _ in candidates if distance == 0]
    if len(direct) > 1:
        return None, "ambiguous"
    if len(direct) == 1:
        return direct[0], "aiming"
    if not candidates:
        return None, "no-target"
    nearest = sorted(candidates, key=lambda item: item[2])
    best = nearest[0]
    # Fill inter-target gaps with bounded direction sectors, not pixel hitboxes.
    if best[1] > OUTER_SNAP:
        return None, "no-target"
    old = next((item for item in candidates if item[0] == previous), None)
    if old and old[1] <= OUTER_SNAP and old[2] <= best[2] + SWITCH_MARGIN:
        return previous, "aiming"
    if len(nearest) > 1 and abs(nearest[1][2] - best[2]) < 0.002:
        return None, "ambiguous"
    return best[0], "aiming"


def clip_segment(a, b, ymin, ymax):
    """Clip a virtual line to one display; phase is assigned before clipping."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, a[0]), (dx, W - a[0]),
                 (-dy, a[1] - ymin), (dy, ymax - a[1])):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            lo = max(lo, q / p)
        else:
            hi = min(hi, q / p)
    if lo > hi:
        return None
    return ((a[0] + dx * lo, a[1] + dy * lo - ymin),
            (a[0] + dx * hi, a[1] + dy * hi - ymin))


def arrow_segments(origin, endpoint, gap, phase=0):
    dx, dy = endpoint[0] - origin[0], endpoint[1] - origin[1]
    length = math.hypot(dx, dy)
    result = [[], []]
    if not length:
        return result
    for start in range(-32, int(length) + 32, 32):
        lo, hi = max(0, start + phase), min(length, start + phase + 19)
        if hi <= lo:
            continue
        a = origin[0] + dx * lo / length, origin[1] + dy * lo / length
        b = origin[0] + dx * hi / length, origin[1] + dy * hi / length
        for screen, offset in enumerate((0, H + gap)):
            segment = clip_segment(a, b, offset, offset + H)
            if segment:
                result[screen].append(segment)
    return result


class Model:
    def __init__(self, emit=lambda event: None):
        self.emit = emit
        self.scene = -1
        self.generation = 0
        self.gap = 48
        self.card = 1
        self.owner = None
        self.gesture = None
        self.target = None
        self.presented = None
        self.origin = None
        self.pointer = None
        self.commits = 0
        self.cancels = 0
        self.status = "ready"
        self.release_pending = False
        self.last_commit = None
        self.change_scene(2)

    def record(self, event, **fields):
        self.emit(dict(event=event, owner=self.owner, gesture=self.gesture,
                       target=self.target, card=CARD_IDS[self.card], slot=self.card, **fields))

    def key(self):
        return self.generation, self.owner, self.gesture, CARD_IDS[self.card], self.target

    def displayed(self):
        self.presented = self.key()
        if self.release_pending:
            self.commit()

    def cancel(self, reason="cancelled"):
        if self.owner:
            self.cancels += 1
            self.record("cancel", reason=reason)
        self.owner = self.gesture = self.target = self.presented = None
        self.origin = self.pointer = None
        self.release_pending = False
        self.status = reason

    def change_scene(self, index):
        self.cancel("scene-change")
        self.scene = index % len(SCENES)
        self.generation += 1
        self.last_commit = None
        self.targets = scene_targets(self.scene, self.generation)
        self.status = "ready"
        self.record("scene", scene=SCENES[self.scene])

    def change_gap(self, delta):
        self.cancel("geometry-change")
        self.gap = max(0, min(160, self.gap + delta))

    def remove_target(self):
        uid = self.target or (self.targets[-1].uid if self.targets else None)
        if self.target == uid:
            self.cancel("target-removed")
        self.targets = [target for target in self.targets if target.uid != uid]
        self.record("remove", removed=uid)

    def down(self, gesture, x, y):
        if self.owner is not None:
            return
        for i, cx in enumerate(CARD_X):
            if abs(x - cx) <= 126 and 462 <= y <= 710:
                self.card, self.owner, self.gesture = i, "touch", gesture
                self.origin = (x, y + H + self.gap)
                self.pointer = self.origin
                self.status = "ready"
                self.record("down", x=x, y=y)
                return

    def move(self, gesture, x, y):
        if self.owner != "touch" or self.gesture != gesture:
            return
        if self.release_pending:
            return
        if not 0 <= x <= W or not 0 <= y <= H:
            self.cancel("edge-loss")
            return
        self.pointer = (x, y + H + self.gap)
        target, status = pick(self.origin, self.pointer, self.targets, self.target)
        if self.status == "aiming" and self.origin[1] - self.pointer[1] < 40:
            self.cancel("drag-back")
            return
        if target != self.target:
            self.presented = None
        self.target, self.status = target, status
        self.record("move", x=x, y=y, status=status)

    def up(self, gesture):
        if self.owner != "touch" or self.gesture != gesture:
            return
        if self.pointer:
            x, y = self.pointer[0], self.pointer[1] - H - self.gap
            # At the physical boundary a lost contact is indistinguishable from UP.
            # Keep aiming visible there, but require an in-panel release to commit.
            if x <= 2 or x >= W - 2 or y <= 2 or y >= H - 2:
                self.cancel("edge-release")
                return
        if self.target is None or not any(t.uid == self.target for t in self.targets):
            self.cancel("invalid-release")
        elif self.presented == self.key():
            self.commit()
        else:
            # A fast flick may deliver move + up in one poll. Freeze its target
            # until the very next presented frame; do not retarget on release.
            self.release_pending = True
            self.record("release-pending")

    def commit(self):
        if self.target is None or self.presented != self.key() or not any(
                target.uid == self.target for target in self.targets):
            self.cancel("invalid-release")
            return
        self.commits += 1
        self.last_commit = dict(number=self.commits, card=self.card, target=self.target,
                                origin=self.pointer or self.origin, endpoint=self.endpoint())
        self.record("commit", number=self.commits)
        self.cancel("committed")
        self.cancels -= 1

    def button(self, key):
        if key == "b":
            self.cancel()
        elif key in ("l", "r"):
            self.change_scene(self.scene + (-1 if key == "l" else 1))
        elif key == "x":
            self.change_scene(self.scene)
        elif key == "y":
            self.remove_target()
        elif key in ("l2", "r2"):
            self.change_gap(-16 if key == "l2" else 16)
        elif key in ("left", "right", "a"):
            if self.owner == "touch":
                self.cancel("pad-takeover")
                self.owner = "pad"
                self.origin = (CARD_X[self.card], CARD_Y + H + self.gap)
                self.target = self.targets[0].uid if self.targets else None
                self.status = "aiming"
                self.record("takeover")
                return
            if self.owner == "pad":
                if key == "a":
                    self.commit()
                elif self.targets:
                    ids = [target.uid for target in self.targets]
                    index = ids.index(self.target) if self.target in ids else 0
                    self.target = ids[(index + (-1 if key == "left" else 1)) % len(ids)]
                    self.presented = None
            elif key == "a":
                self.owner = "pad"
                self.origin = (CARD_X[self.card], CARD_Y + H + self.gap)
                self.target = self.targets[0].uid if self.targets else None
                self.status = "aiming"
            else:
                self.card = (self.card + (-1 if key == "left" else 1)) % 3
            self.record("button", button=key)

    def endpoint(self):
        return next(((t.x, t.y) for t in self.targets if t.uid == self.target), None)

    def arrow_tip(self):
        target = next((t for t in self.targets if t.uid == self.target), None)
        if target is None or self.origin is None:
            return None
        dx, dy = self.origin[0] - target.x, self.origin[1] - target.y
        scale = max(abs(dx) / (target.w / 2 + 5), abs(dy) / (target.h / 2 + 5), 1)
        return target.x + dx / scale, target.y + dy / scale

    def direction_tip(self):
        selected = self.arrow_tip()
        if selected is not None:
            return selected
        if self.owner != "touch" or not self.pointer or not self.origin:
            return None
        dx, up = self.pointer[0] - self.origin[0], self.origin[1] - self.pointer[1]
        if up < AIM_UP:
            return None
        end_y = 130
        return self.origin[0] + dx * (self.origin[1] - end_y) / up, end_y
