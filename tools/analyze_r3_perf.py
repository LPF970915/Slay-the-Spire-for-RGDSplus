"""Join measured swap intervals to Java GC and render timing evidence."""

import argparse
import csv
import json
from pathlib import Path
import re
import statistics

from analyze_frames import summarize


def analyze(rows, log, gc_log, start_ms=0, end_ms=float("inf")):
    probes = []
    for line in log.splitlines():
        if line.startswith("[r3-perf] "):
            probes.append({k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", line)})
    if not probes:
        raise ValueError("No Java monotonic/uptime synchronization samples")
    offset = statistics.median(p["mono_ms"] - p["uptime_ms"] for p in probes)
    pauses = []
    for line in gc_log.splitlines():
        match = re.match(r"\[(\d+)ms\].*GC\((\d+)\) (Pause .*?) ([\d.]+)ms$", line)
        if match:
            uptime, number, reason, duration = match.groups()
            pauses.append(dict(end_ms=offset + int(uptime), duration_ms=float(duration),
                               gc=int(number), reason=reason))
    captures = {i for i, row in enumerate(rows) if int(row["capture"])}
    excluded = {j for i in captures for j in (i-1, i, i+1)}
    slow = []
    for i, row in enumerate(rows):
        end, duration = float(row["monotonic_ms"]), float(row["frame_ms"])
        if i in excluded or not start_ms <= end <= end_ms or duration <= 100:
            continue
        overlap = [p for p in pauses
                   if p["end_ms"] >= end-duration-2 and p["end_ms"]-p["duration_ms"] <= end+2]
        slow.append(dict(end_ms=end, frame_ms=duration, overlapping_gc=overlap))
    intervals = [(float(row["monotonic_ms"]), float(row["frame_ms"]))
                 for i, row in enumerate(rows)
                 if i not in excluded and start_ms <= float(row["monotonic_ms"]) <= end_ms
                 and float(row["frame_ms"]) > 0]
    first, last = intervals[0][0], intervals[-1][0]
    window_probes = [p for p in probes if first <= p["mono_ms"] <= last]
    window_pauses = [p for p in pauses if first <= p["end_ms"] <= last]
    bins = {}
    for timestamp, duration in intervals:
        index = int((timestamp-first) // 5000)
        if first+(index+1)*5000 <= last:
            bins.setdefault(index, []).append(duration)
    rates = [1000/statistics.mean(values) for values in bins.values()]
    return dict(frames=summarize(rows, start_ms, end_ms), uptime_offset_ms=offset,
                gc_pauses=window_pauses, slow_frames=slow, render_windows=window_probes,
                five_second_windows=dict(count=len(rates), min_fps=min(rates) if rates else None,
                                         below_25=sum(rate < 25 for rate in rates)),
                interpretation="GC overlap is correlation, not exclusive attribution")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("log", type=Path)
    parser.add_argument("gc_log", type=Path)
    parser.add_argument("--start-ms", type=float, default=0)
    parser.add_argument("--end-ms", type=float, default=float("inf"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with args.csv.open(newline="") as stream:
        result = analyze(list(csv.DictReader(stream)), args.log.read_text(errors="replace"),
                         args.gc_log.read_text(errors="replace"), args.start_ms, args.end_ms)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result.pop("render_windows")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
