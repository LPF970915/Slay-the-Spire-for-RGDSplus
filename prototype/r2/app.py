"""Silent R2 output, point accuracy and gesture probe."""

import argparse
import ctypes
import json
import math
from pathlib import Path
import signal
import time

from device_input import Devices, dispatch
from p1_display import Display
from probe import POINTS, Probe, SOURCES


class ProbeDisplay(Display):
    def __init__(self, swap=False):
        super().__init__(swap)
        self.lib.SDL_SetWindowTitle.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.SDL_SetWindowTitle.restype = None
        self.lib.SDL_SetWindowTitle(self.window, b"Slay the Spire R2 Touch Probe")

    def cross(self, x, y, color, radius=12):
        self.line((x - radius, y), (x + radius, y), color, 2)
        self.line((x, y - radius), (x, y + radius), color, 2)
        self.rect(x - 3, y - 3, 6, 6, color, False)

    def draw_probe(self, probe, elapsed, fps, diagnostics):
        self.lib.SDL_RenderSetViewport(self.renderer, None)
        self.color((19, 23, 26))
        self.lib.SDL_RenderClear(self.renderer)
        report = probe.report()
        mode = "九点命中" if probe.mode == "grid" else "连续拖动"
        status = {"ready": "待测", "contact": "触摸中", "complete": "采集完成",
                  "released": "已松开", "wrong-point": "非当前点", "moving-tap": "点击中移动"}
        self.viewport(0)
        self.rect(0, 0, 1024, 768, (23, 40, 35))
        self.rect(0, 0, 1024, 86, (14, 23, 24))
        self.text("R2 / 上屏", 30, 23, 34)
        self.text(f"输出 {int(self.swap)}     1024 × 768", 658, 30, 20)
        self.text(mode, 40, 116, 34)
        self.text(status.get(probe.status, "已取消"), 690, 121, 26, (241, 206, 109))
        self.text(f"采样 {len(probe.samples):02d} / 27", 40, 182, 34)
        self.text(f"{fps:05.1f} FPS", 724, 194, 26)
        self.text(f"最大误差  {report['max_error_px']:.2f} px", 40, 255, 26)
        self.text(f"平均误差  {report['mean_error_px']:.2f} px", 40, 303, 26)
        self.text(f"≤ 8px  {report['within_8px']:02d} / {len(probe.samples):02d}", 545, 255, 26)
        self.text(f"错点  {probe.misses}     取消  {probe.cancels}", 545, 303, 26)
        self.line((40, 360), (984, 360), (77, 103, 90))
        for index, (x, y) in enumerate(POINTS):
            cx, cy = 100 + (index % 3) * 126, 420 + (index // 3) * 90
            samples = [s for s in probe.samples if s["expected"] == [x, y]]
            color = (113, 216, 169) if samples else (116, 132, 126)
            self.cross(cx, cy, color, 13)
            label = f"{max(s['error_px'] for s in samples):.1f}" if samples else "--"
            self.text(label, cx + 21, cy - 16, 20, color)
        self.text(f"拖动完成  {probe.drags}", 545, 406, 26)
        self.text(f"原始事件  {diagnostics['raw_events']}", 545, 458, 20)
        self.text(f"完整报告  {diagnostics['reports']}", 545, 500, 20)
        self.text(f"运行  {int(elapsed)//60:02d}:{int(elapsed)%60:02d}", 545, 542, 26)
        if probe.pointer:
            self.text(f"X {probe.pointer[0]:7.2f}   Y {probe.pointer[1]:7.2f}",
                      40, 655, 26)
        source = {"physical-unconfirmed": "实触待签认", "evdev-injection": "软件注入",
                  "model-replay": "模型回放"}[probe.source]
        self.text(source, 735, 718, 20, (241, 206, 109))
        self.viewport(1)
        self.rect(0, 0, 1024, 768, (28, 30, 36))
        for x in range(0, 1024, 64):
            self.line((x, 0), (x, 767), (44, 50, 54))
        for y in range(0, 768, 64):
            self.line((0, y), (1023, y), (44, 50, 54))
        self.rect(0, 0, 1024, 768, (133, 155, 171), False)
        self.text("R2 / 下屏", 420, 100, 34)
        self.text(f"输出 {1-int(self.swap)}     {mode}", 380, 160, 26)
        if probe.mode == "grid":
            for index, (x, y) in enumerate(POINTS):
                selected = (x, y) == probe.expected
                color = (249, 209, 112) if selected else (103, 115, 124)
                self.cross(x, y, color, 13 if selected else 9)
                if selected:
                    self.rect(x - 8, y - 8, 17, 17, color, False)
                label_x = int(x + 22 if x < 950 else x - 54)
                label_y = int(y + 12 if y < 700 else y - 39)
                self.text(str(index + 1), label_x, label_y, 26, color)
            self.text(f"{min(len(probe.samples)+1,27):02d} / 27", 450, 600, 34)
        else:
            points = list(probe.path)
            for a, b in zip(points, points[1:]):
                self.line(a, b, (111, 223, 166), 2)
            # A moving scan marker makes a frozen output visible during idle soak.
            scan_x = 40 + int(elapsed * 120) % 944
            self.rect(scan_x, 704, 10, 24, (237, 184, 112))
        if probe.pointer:
            self.cross(*probe.pointer, (241, 136, 122), radius=6)
        self.lib.SDL_RenderSetViewport(self.renderer, None)


def memory():
    result = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(("VmRSS:", "VmHWM:", "Threads:")):
            fields = line.split()
            result[fields[0][:-1]] = int(fields[1])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--source", choices=SOURCES, default="physical-unconfirmed")
    parser.add_argument("--mode", choices=("grid", "drag"), default="grid")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--swap", action="store_true")
    args = parser.parse_args()
    if args.replay and args.source != "model-replay":
        parser.error("Replay must be explicitly labelled model-replay")
    logs = Path(__file__).resolve().parent / "logs"
    logs.mkdir(exist_ok=True)
    session = str(time.time_ns())
    trace = (logs / f"{session}.jsonl").open("w", encoding="utf-8", buffering=1)

    def emit(event):
        trace.write(json.dumps(dict(t=round(time.monotonic(), 5), **event)) + "\n")

    requested = False
    def request_exit(*_):
        nonlocal requested
        requested = True
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, request_exit)

    probe = Probe(emit, args.source)
    if args.mode == "drag":
        probe.button("r")
    display = ProbeDisplay(args.swap)
    devices = Devices(emit=emit)
    script = json.loads(args.replay.read_text()) if args.replay else []
    step, next_step = 0, 1.5
    started = previous = report_at = time.monotonic()
    frames, fps = 0, 0
    intervals = []
    focused = False
    capture_at = 2.5 if args.capture else math.inf
    try:
        while not requested:
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
                    probe.cancel("focus-loss")
                    actions = []
                elif event == "focus-gain":
                    focused = True
                    devices.set_focus(True)
                    actions = []
            if not focused:
                actions = []
            for action in actions:
                emit(dict(event="input", action=action, source=args.source))
            if not args.replay:
                dispatch(probe, actions)
            capture = None
            if step < len(script) and elapsed >= next_step:
                item = script[step]
                dispatch(probe, [tuple(a) for a in item["actions"]])
                for key, expected in item.get("expect", {}).items():
                    actual = probe.report()[key]
                    if actual != expected:
                        raise AssertionError(f"Step {step}: {key}={actual}, expected {expected}")
                emit(dict(event="replay", step=step))
                if item.get("capture"):
                    capture = logs / f"{session}-{step}.ppm"
                next_step = elapsed + item.get("wait", .025)
                step += 1
                if step == len(script):
                    emit(dict(event="replay-passed", steps=step, report=probe.report()))
            display.draw_probe(probe, elapsed, fps, devices.diagnostics())
            if elapsed >= capture_at:
                capture = logs / f"{session}-initial.ppm"
                capture_at = math.inf
            if capture:
                display.capture(capture)
            display.present()
            probe.displayed()
            end = time.monotonic()
            frames += 1
            intervals.append((end - previous) * 1000)
            previous = end
            if end - report_at >= 2:
                fps = len(intervals) / (end - report_at)
                values = sorted(intervals)
                state = dict(session=session, frames=frames, seconds=round(end - started, 2),
                             fps=round(fps, 2), p95_ms=round(values[int(len(values)*.95)], 2),
                             max_ms=round(max(values), 2), memory=memory(), probe=probe.report(),
                             touch=devices.diagnostics(), replay_steps=step)
                emit(dict(event="performance", **state))
                temp = logs / "state.tmp"
                temp.write_text(json.dumps(state))
                temp.replace(logs / "state.json")
                intervals.clear()
                report_at = end
            time.sleep(max(0, 1/60 - (end-now)))
    finally:
        probe.cancel("shutdown")
        result = dict(session=session, seconds=time.monotonic()-started, frames=frames,
                      replay_steps=step, probe=probe.report(), samples=probe.samples)
        (logs / f"{session}-result.json").write_text(json.dumps(result, indent=2))
        emit(dict(event="exit", **result))
        devices.close()
        display.close()
        trace.close()
    if step != len(script):
        raise RuntimeError(f"Incomplete replay {step}/{len(script)}")


if __name__ == "__main__":
    main()
