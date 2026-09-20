"""Check saved R3 evidence without upgrading it to physical acceptance."""

import csv
import json
from pathlib import Path

from analyze_frames import summarize

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "validation/r3-native-ui"


def main():
    def shot(name):
        return json.loads((EVIDENCE / (name + "-state.json")).read_text())

    battle = shot("08-battle-layout")
    targeting = shot("09-target-layout")
    discard = shot("10-discard-layout")
    draw = shot("11-draw-layout")
    before, after = targeting["state.xml"], discard["state.xml"]
    assert before["hoveredCard.cardID"] == "Strike_R"
    assert before["player.inSingleTargetMode"] == "true"
    assert before["hoveredMonster.currentHealth"] == "14"
    assert (before["energy.totalCount"], after["energy.totalCount"]) == ("3", "2")
    assert (before["hand.count"], after["hand.count"]) == ("5", "4")
    assert (before["discardPile.count"], after["discardPile.count"]) == ("0", "1")
    assert after["discardPile.0.cardID"] == "Strike_R"
    assert (before["monsters.1.currentHealth"], after["monsters.1.currentHealth"]) == ("14", "8")
    assert before["monsters.0.currentHealth"] == after["monsters.0.currentHealth"] == "12"
    assert after["dungeon.screen"] == "DISCARD_VIEW"
    assert draw["state.xml"]["dungeon.screen"] == "GAME_DECK_VIEW"
    for state in (battle, targeting, discard, draw):
        assert state["dual-state.xml"]["frames"] == state["dual-state.xml"]["updates"]
        assert state["dual-state.xml"]["touchPolicy"] == "capture-only"
    with (EVIDENCE / "frames-23671.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    start = int(battle["state.xml"]["monotonicNs"]) / 1e6
    report = {
        "input_source": "evdev-injection",
        "physical_acceptance": False,
        "real_game_touch_submission": False,
        "controlled_strike_samples": 1,
        "checks": "Single cost, card removal, discard insertion and correct enemy damage",
        "frames_equal_updates_at_four_snapshots": True,
        "frame_source": "frames-23671.csv",
        "whole_session": summarize(rows),
        "from_battle_screenshot_to_session_end": summarize(rows, start),
        "limits": [
            "Not 200 interactions or 30-minute endurance",
            "Only capture-neighbor intervals excluded; loading stalls retained",
            "Screenshots are native framebuffer captures, not physical-panel photographs",
        ],
    }
    destination = EVIDENCE / "evidence-summary.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
