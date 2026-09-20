"""Build deterministic on-device visual/input-ownership verification cases."""

import json
from pathlib import Path

from geometry import CARD_X, CARD_Y, H, scene_targets


def build():
    steps = []
    commits = 0
    gesture = 100
    generation = 1

    def add(actions, expect=None, capture=False):
        steps.append(dict(actions=actions, expect=expect or {},
                          capture=capture, wait=0.05))

    for repeat in range(6):
        for scene in (0, 1, 2, 4):
            generation += 1
            add([["change_scene", scene]])
            targets = scene_targets(scene, generation)
            for card, x in enumerate(CARD_X):
                for index, target in enumerate(targets):
                    gesture += 1
                    add([["down", gesture, x, CARD_Y]])
                    px = x + (target.x - x) * 0.3
                    py = CARD_Y + (target.y - CARD_Y - H - 48) * 0.3
                    capture = repeat == 0 and card == 0 and index == len(targets) - 1
                    add([["move", gesture, px, py]],
                        dict(target=target.uid, owner="touch"), capture)
                    commits += 1
                    add([["up", gesture]], dict(commits=commits, owner=None))
    add([["change_scene", 3]])
    add([["down", 999, 512, CARD_Y]])
    add([["move", 999, 512, 273]], dict(target=None, status="ambiguous"), True)
    add([["up", 999]], dict(commits=commits))
    for i in range(18):
        add([["button", "a"]], dict(owner="pad"))
        add([["button", "right"]], capture=i == 0)
        commits += 1
        add([["button", "a"]], dict(commits=commits, owner=None))
    add([["change_scene", 2]])
    for index in range(40):
        gesture += 1
        add([["down", gesture, 512, 590]])
        add([["move", gesture, 512, 273]])
        add([["cancel", ("focus-loss", "syn-dropped", "second-finger",
                         "disconnect")[index % 4]], ["up", gesture]],
            dict(owner=None, commits=commits))
    add([["down", 5001, 512, 590]])
    add([["move", 5001, 512, 273]])
    add([["button", "right"], ["up", 5001]], dict(owner="pad", commits=commits))
    commits += 1
    add([["button", "a"]], dict(owner=None, commits=commits))
    add([["down", 5002, 512, 590]])
    add([["move", 5002, 512, 273]])
    add([["remove_target"], ["up", 5002]], dict(owner=None, commits=commits))
    add([["change_scene", 2]], dict(commits=commits), True)
    generation += 3  # overlap, return-to-five, and final reset above
    gap = 48
    for next_gap in (0, 48, 96):
        add([["change_gap", next_gap - gap]])
        gap = next_gap
        targets = scene_targets(2, generation)
        for card, x in enumerate(CARD_X):
            for target in targets:
                gesture += 1
                add([["down", gesture, x, CARD_Y]])
                for y in (200, 80, 8):
                    px = x + (target.x - x) * (CARD_Y - y) / (CARD_Y + H + gap - target.y)
                    add([["move", gesture, px, y]], dict(target=target.uid, owner="touch"),
                        card == 0 and target == targets[-1] and y == 8)
                commits += 1
                add([["up", gesture]], dict(commits=commits, owner=None))
    for card, x in enumerate(CARD_X):
        for target in targets:
            gesture += 1
            px = x + (target.x - x) * .3
            py = CARD_Y + (target.y - CARD_Y - H - gap) * .3
            add([["down", gesture, x, CARD_Y], ["move", gesture, px, py], ["up", gesture]],
                dict(commits=commits, release_pending=True, target=target.uid))
            commits += 1
            add([], dict(commits=commits, owner=None), card == 0 and target == targets[-1])
    add([["change_gap", 48 - gap]])
    add([["down", 9901, 512, 590], ["move", 9901, 512, 0]],
        dict(target=targets[2].uid, owner="touch"), True)
    add([["up", 9901]], dict(commits=commits, owner=None, status="edge-release"))
    add([["change_scene", 3], ["down", 9902, 512, 590], ["move", 9902, 512, 200]],
        dict(target=None, status="ambiguous"), True)
    add([["up", 9902]], dict(commits=commits, owner=None))
    add([["change_scene", 2]], dict(commits=commits), True)
    return steps


if __name__ == "__main__":
    steps = build()
    Path(__file__).with_name("replay.json").write_text(json.dumps(steps, indent=2) + "\n")
    print(f"Generated {len(steps)} steps, {steps[-1]['expect']['commits']} expected commits")
