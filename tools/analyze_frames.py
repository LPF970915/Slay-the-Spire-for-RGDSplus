"""Summarize an explicit frame-time window without hiding slow frames."""

import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def summarize(rows, start_ms=0, end_ms=math.inf):
    captures = {i for i, row in enumerate(rows) if int(row["capture"])}
    readback = {j for i in captures for j in (i - 1, i, i + 1)}
    window = [(i, row) for i, row in enumerate(rows)
              if start_ms <= float(row["monotonic_ms"]) <= end_ms
              and float(row["frame_ms"]) > 0]
    values = sorted(float(row["frame_ms"]) for i, row in window if i not in readback)
    if not values:
        raise ValueError("No complete non-capture intervals in this window")
    return {
        "first_ms": float(window[0][1]["monotonic_ms"]),
        "last_ms": float(window[-1][1]["monotonic_ms"]),
        "frames": len(values),
        "capture_neighbor_intervals_excluded": sum(i in readback for i, _ in window),
        "mean_ms": statistics.mean(values),
        "fps_from_mean": 1000 / statistics.mean(values),
        "p95_ms": values[math.ceil(len(values) * .95) - 1],
        "p99_ms": values[math.ceil(len(values) * .99) - 1],
        "max_ms": values[-1],
        "over_100_ms": sum(value > 100 for value in values),
        "over_250_ms": sum(value > 250 for value in values),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--start-ms", type=float, default=0)
    parser.add_argument("--end-ms", type=float, default=math.inf)
    args = parser.parse_args()
    if args.end_ms <= args.start_ms:
        parser.error("end must follow start")
    with args.csv.open(newline="", encoding="utf-8") as stream:
        result = summarize(list(csv.DictReader(stream)), args.start_ms, args.end_ms)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
