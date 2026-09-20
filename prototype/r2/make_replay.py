"""R2 software-path coverage, intentionally labelled separately from physical QA."""

import json
from pathlib import Path

from probe import POINTS


def build():
    steps = []
    def add(actions, expected=None, capture=False):
        steps.append(dict(actions=actions, expect=expected or {}, capture=capture, wait=.025))
    uid = 0
    for index in range(27):
        x, y = POINTS[index % 9]
        uid += 1
        add([["down", uid, x, y], ["up", uid]], dict(samples=index + 1), index in (8, 26))
    add([], dict(complete=True, measured_pass=True, physical_verified=False), True)
    add([["button", "r"]])
    for index in range(220):
        uid += 1
        x = 16 + index % 9 * 120
        add([["down", uid, x, 740]])
        add([["move", uid, 512, 384], ["move", uid, 1008-x, 8]])
        add([["up", uid]], dict(drags=index + 1), index == 219)
    for index in range(24):
        uid += 1
        add([["down", uid, 512, 590], ["move", uid, 512, 100]])
        add([["cancel", ("focus-loss", "syn-dropped", "second-finger", "disconnect")[index % 4]],
             ["up", uid]], dict(drags=220, cancels=index + 1))
    add([], dict(drags=220, cancels=24, physical_verified=False), True)
    return steps


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[2] / "dist/r2-replay.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(build(), indent=2))
    print(output)
