"""Silent native SDL2 geometry probe. Uses only firmware libraries and fonts."""

import argparse
import ctypes as C
import json
import math
from pathlib import Path
import statistics
import time

from device_input import Devices, dispatch
from geometry import Model, W, H, CARD_X, arrow_segments, clip_segment


class Rect(C.Structure):
    _fields_ = [(key, C.c_int) for key in ("x", "y", "w", "h")]


class Color(C.Structure):
    _fields_ = [(key, C.c_uint8) for key in ("r", "g", "b", "a")]


class Display:
    def __init__(self, swap=False):
        self.lib = C.CDLL("libSDL2-2.0.so.0")
        self.ttf = C.CDLL("libSDL2_ttf-2.0.so.0")
        p, i, s = C.c_void_p, C.c_int, C.c_char_p
        signatures = {
            "SDL_Init": (i, [C.c_uint32]),
            "SDL_GetError": (s, []),
            "SDL_SetHint": (i, [s, s]),
            "SDL_GetNumVideoDisplays": (i, []),
            "SDL_GetDisplayBounds": (i, [i, C.POINTER(Rect)]),
            "SDL_CreateWindow": (p, [s, i, i, i, i, C.c_uint32]),
            "SDL_CreateRenderer": (p, [p, i, C.c_uint32]),
            "SDL_GetRendererOutputSize": (i, [p, C.POINTER(i), C.POINTER(i)]),
            "SDL_PollEvent": (i, [p]),
            "SDL_SetRenderDrawColor": (i, [p, C.c_uint8, C.c_uint8, C.c_uint8, C.c_uint8]),
            "SDL_RenderClear": (i, [p]),
            "SDL_RenderSetViewport": (i, [p, C.POINTER(Rect)]),
            "SDL_RenderDrawRect": (i, [p, C.POINTER(Rect)]),
            "SDL_RenderFillRect": (i, [p, C.POINTER(Rect)]),
            "SDL_RenderDrawLine": (i, [p, i, i, i, i]),
            "SDL_RenderPresent": (None, [p]),
            "SDL_CreateTextureFromSurface": (p, [p, p]),
            "SDL_QueryTexture": (i, [p, p, p, C.POINTER(i), C.POINTER(i)]),
            "SDL_RenderCopy": (i, [p, p, p, C.POINTER(Rect)]),
            "SDL_FreeSurface": (None, [p]),
            "SDL_DestroyTexture": (None, [p]),
            "SDL_RenderReadPixels": (i, [p, p, C.c_uint32, p, i]),
            "SDL_DestroyRenderer": (None, [p]),
            "SDL_DestroyWindow": (None, [p]),
            "SDL_Quit": (None, []),
        }
        for name, (restype, args) in signatures.items():
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = restype, args
        for name, restype, args in (
            ("TTF_Init", i, []), ("TTF_OpenFont", p, [s, i]),
            ("TTF_RenderUTF8_Blended", p, [p, s, Color]),
            ("TTF_CloseFont", None, [p]), ("TTF_Quit", None, []),
        ):
            fn = getattr(self.ttf, name)
            fn.restype, fn.argtypes = restype, args
        self.lib.SDL_SetHint(b"SDL_TOUCH_MOUSE_EVENTS", b"0")
        self.lib.SDL_SetHint(b"SDL_MOUSE_TOUCH_EVENTS", b"0")
        self.lib.SDL_SetHint(b"SDL_RENDER_DRIVER", b"opengles2")
        self.check(self.lib.SDL_Init(0x20))
        bounds = []
        for index in range(self.lib.SDL_GetNumVideoDisplays()):
            rect = Rect()
            self.check(self.lib.SDL_GetDisplayBounds(index, C.byref(rect)))
            bounds.append([rect.x, rect.y, rect.w, rect.h])
        if sorted(bounds) != [[0, 0, 1024, 768], [1024, 0, 1024, 768]]:
            raise RuntimeError(f"Unsupported output layout; no firmware changes made: {bounds}")
        self.window = self.lib.SDL_CreateWindow(b"Slay the Spire P1 Geometry", 0, 0,
                                                 2048, 768, 0x14)
        if not self.window:
            raise RuntimeError(self.lib.SDL_GetError().decode())
        self.renderer = self.lib.SDL_CreateRenderer(self.window, -1, 2 | 4)
        if not self.renderer:
            raise RuntimeError(self.lib.SDL_GetError().decode())
        width, height = i(), i()
        self.check(self.lib.SDL_GetRendererOutputSize(
            self.renderer, C.byref(width), C.byref(height)))
        if (width.value, height.value) != (2048, 768):
            raise RuntimeError(f"Unexpected framebuffer {width.value}x{height.value}")
        self.check(self.ttf.TTF_Init())
        font = b"/usr/share/fonts/source-han-sans-cn/SourceHanSansCN-Regular.otf"
        self.fonts = {size: self.ttf.TTF_OpenFont(font, size) for size in (20, 26, 34, 46)}
        if not all(self.fonts.values()):
            raise RuntimeError("Firmware Chinese font missing")
        self.textures = {}
        self.swap = swap
        self.event = C.create_string_buffer(64)
        print(json.dumps(dict(event="display", bounds=bounds, framebuffer=[2048, 768],
                              swap=swap, audio=False)), flush=True)

    def check(self, result):
        if result < 0:
            raise RuntimeError(self.lib.SDL_GetError().decode())

    def events(self):
        events = []
        while self.lib.SDL_PollEvent(self.event):
            raw = self.event.raw
            kind = int.from_bytes(raw[:4], "little")
            if kind == 0x100:
                events.append("quit")
            if kind == 0x200 and raw[12] in (2, 7, 13):
                events.append("focus-loss")
            if kind == 0x200 and raw[12] == 12:
                events.append("focus-gain")
        return events

    def color(self, rgb):
        self.lib.SDL_SetRenderDrawColor(self.renderer, *rgb, 255)

    def rect(self, x, y, w, h, color, fill=True):
        self.color(color)
        rect = Rect(int(x), int(y), int(w), int(h))
        fn = self.lib.SDL_RenderFillRect if fill else self.lib.SDL_RenderDrawRect
        fn(self.renderer, C.byref(rect))

    def line(self, a, b, color, width=1):
        self.color(color)
        for offset in range(width):
            self.lib.SDL_RenderDrawLine(self.renderer, int(a[0]), int(a[1]) + offset,
                                       int(b[0]), int(b[1]) + offset)

    def text(self, value, x, y, size=26, color=(230, 237, 233)):
        key = value, size, color
        if key not in self.textures:
            if len(self.textures) > 256:
                for texture, _, _ in self.textures.values():
                    self.lib.SDL_DestroyTexture(texture)
                self.textures.clear()
            surface = self.ttf.TTF_RenderUTF8_Blended(
                self.fonts[size], value.encode("utf-8"), Color(*color, 255))
            if not surface:
                raise RuntimeError("Font rasterization failed")
            texture = self.lib.SDL_CreateTextureFromSurface(self.renderer, surface)
            self.lib.SDL_FreeSurface(surface)
            if not texture:
                raise RuntimeError("Font texture upload failed")
            w, h = C.c_int(), C.c_int()
            self.check(self.lib.SDL_QueryTexture(texture, None, None, C.byref(w), C.byref(h)))
            self.textures[key] = texture, w.value, h.value
        texture, w, h = self.textures[key]
        self.lib.SDL_RenderCopy(self.renderer, texture, None, C.byref(Rect(x, y, w, h)))

    def viewport(self, screen):
        x = (1 - screen if self.swap else screen) * W
        self.lib.SDL_RenderSetViewport(self.renderer, C.byref(Rect(x, 0, W, H)))

    def draw(self, m, elapsed, fps):
        self.lib.SDL_RenderSetViewport(self.renderer, None)
        self.color((22, 27, 28))
        self.lib.SDL_RenderClear(self.renderer)
        selected = m.target.split(":")[-1] if m.target else "--"
        self.viewport(0)
        self.rect(0, 0, W, H, (23, 42, 38))
        # Original geometric scenery, not captured or extracted game artwork.
        for x, height in ((0, 150), (180, 240), (380, 180), (650, 220), (880, 150)):
            self.rect(x, 520 - height, 130, height, (29, 51, 44))
        self.rect(0, 565, W, 203, (35, 43, 42))
        for x in range(0, W, 64):
            self.line((512 + (x - 512) * 0.45, 565), (x, 768), (52, 62, 56))
        for y in (600, 658, 740):
            self.line((0, y), (W, y), (52, 62, 56))
        self.rect(0, 0, W, 82, (16, 25, 26))
        self.text("P1  /  目标场", 28, 21, 26)
        self.text("选中 " + selected, 410, 21)
        self.text(f"1024 × 768    {fps:02.0f} FPS", 695, 25, 20)
        for t in m.targets:
            active = t.uid == m.target
            color = (103, 218, 167) if active else (171, 179, 184)
            x, y = t.x - t.w / 2, t.y - t.h / 2
            self.rect(x + 6, y + t.h + 10, t.w - 12, 8, (15, 24, 24))
            self.rect(x, y, t.w, t.h, (56, 79, 70) if active else (61, 68, 72))
            for d in range(4 if active else 1):
                self.rect(x - d, y - d, t.w + 2 * d, t.h + 2 * d, color, False)
            self.text(t.uid.split(":")[-1], int(t.x - 15), int(t.y - 33), 46, color)
            self.line((t.x - 24, t.y + 42), (t.x + 24, t.y + 42), color, 3)
            if active:
                pulse = 9 + 3 * math.sin(elapsed * 5)
                self.line((t.x - pulse, y - 25), (t.x, y - 14), color, 3)
                self.line((t.x, y - 14), (t.x + pulse, y - 25), color, 3)
        self.viewport(1)
        self.rect(0, 0, W, H, (27, 31, 35))
        self.rect(0, 0, W, 82, (16, 25, 26))
        names = ("单目标", "双目标", "五目标", "重叠目标", "两侧包围")
        self.text(names[m.scene], 102, 21)
        self.text(f"间距 {m.gap}", 740, 25, 20)
        self.text("<", 36, 17, 34)
        self.text(">", 340, 17, 34)
        statuses = {"ready": "待选牌", "aiming": "目标 " + selected,
                    "ambiguous": "目标重叠", "no-target": "无目标",
                    "committed": "已提交", "cancelled": "已取消"}
        self.text(statuses.get(m.status, "已取消"), 36, 108, 34,
                  (103, 218, 167) if m.target else (236, 206, 115))
        self.text(f"提交 {m.commits}    取消 {m.cancels}", 692, 116, 20)
        for x in range(32, W, 64):
            self.line((x, 196), (x, 432), (39, 46, 50))
        for y in range(196, 440, 48):
            self.line((32, y), (992, y), (39, 46, 50))
        # Lower decorative foreground stays behind cards, never on upper output.
        self.rect(0, 650, W, 118, (43, 57, 50))
        for x in (0, 275, 715, 970):
            self.rect(x, 622, 48, 28, (51, 70, 58))
        for i, x in enumerate(CARD_X):
            active = i == m.card
            top = 462 if active else 480
            self.rect(x - 126, top, 252, 228, (70, 77, 82) if active else (46, 52, 58))
            edge = (103, 218, 167) if active else (106, 117, 123)
            for d in range(3 if active else 1):
                self.rect(x - 126 + d, top + d, 252 - d * 2, 228 - d * 2, edge, False)
            self.text(f"C{i + 1}", x - 30, top + 23, 34, edge)
            self.line((x - 30, top + 120), (x, top + 80), edge, 3)
            self.line((x, top + 80), (x + 30, top + 120), edge, 3)
            self.line((x, top + 80), (x, top + 152), edge, 3)
            self.text(("左位", "中位", "右位")[i], x - 26, top + 181, 26)
        self.text("GEOMETRY  /  无游戏资源", 28, 727, 20, (157, 179, 166))
        self.text({"touch": "触摸", "pad": "手柄"}.get(m.owner, "--"), 918, 727, 20)
        endpoint = m.direction_tip()
        arrow_color = (248, 219, 125) if m.target else (136, 151, 157)
        if endpoint and m.origin:
            segments = arrow_segments(m.origin, endpoint, m.gap, int(elapsed * 28) % 32)
            for screen, paths in enumerate(segments):
                self.viewport(screen)
                for a, b in paths:
                    if screen == 1:
                        # The stationary hand is in front of the aiming path.
                        segment = clip_segment(a, b, 0, 451)
                        if segment is None:
                            continue
                        a, b = segment
                    self.line(a, b, arrow_color, 3)
            self.viewport(0)
            dx, dy = endpoint[0] - m.origin[0], endpoint[1] - m.origin[1]
            length = math.hypot(dx, dy)
            ux, uy = dx / length, dy / length
            for sign in (-1, 1):
                end = endpoint[0] - ux * 24 + sign * uy * 12, endpoint[1] - uy * 24 - sign * ux * 12
                self.line(endpoint, end, arrow_color, 3)
        if m.owner == "touch" and m.pointer:
            self.viewport(1)
            x, y = m.pointer[0], m.pointer[1] - H - m.gap
            if m.pointer != m.origin:
                cx, cy = max(72, min(W - 72, x)), max(90, min(H - 90, y))
                self.rect(cx - 72, cy - 90, 144, 180, (69, 90, 78))
                self.rect(cx - 72, cy - 90, 144, 180, (103, 218, 167), False)
                self.text(f"C{m.card + 1}", int(cx - 29), int(cy - 62), 34)
                self.line((cx - 22, cy + 24), (cx, cy - 5), (236, 206, 115), 3)
                self.line((cx, cy - 5), (cx + 22, cy + 24), (236, 206, 115), 3)
            self.line((x - 12, y), (x + 12, y), (247, 240, 211), 2)
            self.line((x, y - 12), (x, y + 12), (247, 240, 211), 2)
        if m.last_commit:
            if getattr(self, "flight_number", None) != m.last_commit["number"]:
                self.flight_number = m.last_commit["number"]
                self.flight_started = elapsed
            progress = (elapsed - self.flight_started) / 0.28
            if 0 <= progress <= 1:
                start, end = m.last_commit["origin"], m.last_commit["endpoint"]
                amount = 1 - (1 - progress) ** 2
                x = start[0] + (end[0] - start[0]) * amount
                y = start[1] + (end[1] - start[1]) * amount
                width, height = 52 - 24 * progress, 70 - 32 * progress
                for screen, offset in enumerate((0, H + m.gap)):
                    self.viewport(screen)
                    self.rect(x - width / 2, y - offset - height / 2, width, height,
                              (236, 206, 115))
                    self.rect(x - width / 2, y - offset - height / 2, width, height,
                              (103, 218, 167), False)
        self.lib.SDL_RenderSetViewport(self.renderer, None)

    def capture(self, path):
        pixels = C.create_string_buffer(2048 * 768 * 3)
        self.check(self.lib.SDL_RenderReadPixels(
            self.renderer, None, 0x17101803, pixels, 2048 * 3))
        path.write_bytes(b"P6\n2048 768\n255\n" + pixels.raw)

    def present(self):
        self.lib.SDL_RenderPresent(self.renderer)

    def close(self):
        for texture, _, _ in self.textures.values():
            self.lib.SDL_DestroyTexture(texture)
        for font in self.fonts.values():
            self.ttf.TTF_CloseFont(font)
        self.ttf.TTF_Quit()
        self.lib.SDL_DestroyRenderer(self.renderer)
        self.lib.SDL_DestroyWindow(self.window)
        self.lib.SDL_Quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--swap", action="store_true")
    args = parser.parse_args()
    logs = Path(__file__).resolve().parent / "logs"
    logs.mkdir(exist_ok=True)
    session = str(time.time_ns())
    trace = (logs / f"{session}.jsonl").open("w", encoding="utf-8", buffering=1)

    def emit(event):
        trace.write(json.dumps(dict(t=round(time.monotonic(), 4), **event)) + "\n")

    model = Model(emit)
    display = Display(args.swap)
    devices = Devices(emit=emit)
    script = json.loads(args.replay.read_text()) if args.replay else []
    step = 0
    next_step = 1.5
    started = previous = report = time.monotonic()
    intervals = []
    fps = 0
    frames = 0
    captured = False
    focused = False
    try:
        while True:
            now = time.monotonic()
            elapsed = now - started
            if args.seconds and elapsed >= args.seconds:
                break
            actions = devices.poll(now)
            events = display.events()
            if "quit" in events:
                break
            for event in events:
                emit(dict(event=event))
                if event == "focus-loss":
                    focused = False
                    devices.set_focus(False)
                    devices.cancel_touch()
                    model.cancel("focus-loss")
                    actions = []
                elif event == "focus-gain":
                    focused = True
                    devices.set_focus(True)
                    actions = []
                    if not model.owner:
                        model.status = "ready"
            if not focused:
                actions = []
            # Native SDL touch/mouse/key events are never consumed a second time.
            cancelled = any(a[0] == "cancel" or a == ("button", "b") for a in actions)
            for action in actions:
                emit(dict(event="input", action=action))
                if not cancelled and action[0] == "down" and action[3] < 82:
                    if action[2] < 80:
                        model.button("l")
                    elif 300 < action[2] < 400:
                        model.button("r")
            dispatch(model, actions)
            capture = None
            if step < len(script) and elapsed >= next_step:
                item = script[step]
                dispatch(model, [tuple(action) for action in item.get("actions", [])])
                for key, expected in item.get("expect", {}).items():
                    actual = getattr(model, key)
                    if actual != expected:
                        raise AssertionError(f"Replay {step}: {key}={actual!r}, expected {expected!r}")
                if item.get("capture"):
                    capture = logs / f"{session}-{step}.ppm"
                emit(dict(event="replay", step=step))
                next_step = elapsed + item.get("wait", 0.06)
                step += 1
                if step == len(script):
                    emit(dict(event="replay-passed", steps=step, commits=model.commits))
            display.draw(model, elapsed, fps)
            if args.capture and not captured and elapsed > 1:
                capture = logs / f"{session}-initial.ppm"
                captured = True
            if capture:
                display.capture(capture)
            display.present()
            model.displayed()
            end = time.monotonic()
            frames += 1
            intervals.append((end - previous) * 1000)
            previous = end
            if end - report >= 2:
                fps = len(intervals) / (end - report)
                values = sorted(intervals)
                state = dict(session=session, frames=frames, seconds=round(end - started, 2),
                             fps=round(fps, 2), p95_ms=round(values[int(len(values) * 0.95)], 2),
                             max_ms=round(max(values), 2), median_ms=round(statistics.median(values), 2),
                             scene=model.scene, owner=model.owner, target=model.target,
                             commits=model.commits, cancels=model.cancels, replay_steps=step,
                             touch=devices.diagnostics())
                emit(dict(event="performance", **state))
                temp = logs / "state.tmp"
                temp.write_text(json.dumps(state), encoding="utf-8")
                temp.replace(logs / "state.json")
                intervals.clear()
                report = end
            # Also bound CPU usage if the firmware ignores swap interval.
            time.sleep(max(0, 1 / 60 - (end - now)))
    finally:
        emit(dict(event="exit", frames=frames, commits=model.commits, replay_steps=step))
        devices.close()
        display.close()
        trace.close()
    if step != len(script):
        raise RuntimeError(f"Replay incomplete: {step}/{len(script)}")


if __name__ == "__main__":
    main()
