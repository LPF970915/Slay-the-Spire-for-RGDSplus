"""R2 measurements only: no calibration writes, target snapping or game state."""

from collections import deque
import math

POINTS = tuple((x, y) for y in (16, 384, 752) for x in (16, 512, 1008))
REPEATS = 3
SOURCES = ("physical-unconfirmed", "evdev-injection", "model-replay")


class Probe:
    def __init__(self, emit=lambda event: None, source="physical-unconfirmed"):
        if source not in SOURCES:
            raise ValueError("Explicit evidence source required")
        self.emit = emit
        self.source = source
        self.mode = "grid"
        self.run = 0
        self.owner = None
        self.pointer = None
        self.start = None
        self.presented = None
        self.samples = []
        self.path = deque(maxlen=512)
        self.distance = 0
        self.peak = 0
        self.drags = 0
        self.cancels = 0
        self.misses = 0
        self.status = "ready"
        self.reset()

    @property
    def complete(self):
        return len(self.samples) == len(POINTS) * REPEATS

    @property
    def expected(self):
        return None if self.complete else POINTS[len(self.samples) % len(POINTS)]

    def reset(self):
        if self.run:
            self.emit(dict(event="probe-run-end", **self.report()))
        self.cancel("reset")
        self.run += 1
        self.samples.clear()
        self.path.clear()
        self.pointer = None
        self.presented = None
        self.drags = self.cancels = self.misses = 0
        self.status = "ready"
        self.emit(dict(event="probe-run", run=self.run, mode=self.mode, source=self.source))

    def displayed(self):
        self.presented = (self.run, self.mode, len(self.samples))

    def button(self, key):
        if key == "b":
            self.cancel("button")
        elif key == "x":
            self.reset()
        elif key in ("l", "r"):
            self.cancel("mode-change")
            self.mode = "drag" if self.mode == "grid" else "grid"
            self.presented = None
            self.status = "ready"
            self.emit(dict(event="probe-mode", run=self.run, mode=self.mode))

    def cancel(self, reason):
        if self.owner is not None:
            self.cancels += 1
            self.emit(dict(event="probe-cancel", run=self.run, gesture=self.owner, reason=reason))
        self.owner = self.start = None
        self.status = reason

    def down(self, gesture, x, y):
        if self.owner is not None:
            self.cancel("duplicate-down")
            return
        if not 0 <= x <= 1024 or not 0 <= y <= 768:
            return
        if self.mode == "grid" and (self.complete or
                self.presented != (self.run, self.mode, len(self.samples))):
            return
        self.owner, self.pointer, self.start = gesture, (x, y), (x, y)
        self.peak = self.distance = 0
        self.path.clear()
        self.path.append((x, y))
        self.status = "contact"
        self.emit(dict(event="probe-down", run=self.run, gesture=gesture, x=x, y=y))

    def move(self, gesture, x, y):
        if gesture != self.owner or self.owner is None:
            return
        if not 0 <= x <= 1024 or not 0 <= y <= 768:
            self.cancel("outside")
            return
        self.distance += math.dist(self.pointer, (x, y))
        self.pointer = (x, y)
        self.peak = max(self.peak, math.dist(self.start, self.pointer))
        self.path.append(self.pointer)

    def up(self, gesture):
        if gesture != self.owner or self.owner is None:
            return
        if self.mode == "grid":
            if self.peak > 12:
                self.cancel("moving-tap")
                return
            x, y = self.start
            tx, ty = self.expected
            error = math.hypot(x - tx, y - ty)
            sample = dict(run=self.run, number=len(self.samples) + 1,
                          expected=[tx, ty], measured=[x, y], dx=x - tx, dy=y - ty,
                          error_px=error, gesture=gesture, source=self.source)
            if error > 96:
                self.misses += 1
                self.emit(dict(event="probe-miss", **sample))
                self.cancel("wrong-point")
                return
            self.samples.append(sample)
            self.emit(dict(event="probe-sample", **sample))
            self.presented = None
            self.status = "complete" if self.complete else "ready"
        else:
            self.drags += 1
            self.emit(dict(event="probe-drag", run=self.run, number=self.drags,
                           gesture=gesture, distance_px=self.distance,
                           start=self.start, end=self.pointer))
            self.status = "released"
        self.owner = self.start = None

    def report(self):
        errors = [s["error_px"] for s in self.samples]
        return dict(run=self.run, mode=self.mode, source=self.source, samples=len(self.samples),
                    expected_samples=len(POINTS) * REPEATS, complete=self.complete,
                    max_error_px=max(errors, default=0), mean_error_px=sum(errors) / max(1, len(errors)),
                    within_8px=sum(e <= 8 for e in errors), misses=self.misses,
                    drags=self.drags, cancels=self.cancels, status=self.status,
                    measured_pass=self.complete and all(e <= 8 for e in errors) and self.misses == 0,
                    physical_verified=False)
