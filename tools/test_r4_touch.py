"""Native touch transport tests; not physical-panel acceptance."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype/r3"))
from touch_transport import TouchTransport, PACKET


class Sink:
    def __init__(self):
        self.packets = []

    def sendall(self, data):
        self.packets.append(PACKET.unpack(data))

    def close(self):
        pass


class NativeTouchTests(unittest.TestCase):
    def setUp(self):
        self.bridge = TouchTransport(Path("."), clock=lambda: 10)
        self.sink = Sink()
        self.bridge.socket = self.sink

    def test_ordered_final_move_and_repeat(self):
        for token in (1, 2):
            self.bridge.actions([("down", token, 512, 700), ("move", token, 520, 200),
                                 ("up", token)], True)
        packets = self.sink.packets
        self.assertEqual([p[1] for p in packets], [1, 2, 3, 1, 2, 3])
        self.assertEqual(packets[2][3:5], (520, 200))
        self.assertNotEqual(packets[0][-1], packets[3][-1])

    def test_cancel_or_pad_wins_release_batch(self):
        for action in (("cancel", "second-finger"), ("button", "b"), ("button", "left")):
            self.bridge.actions([("down", 1, 50, 60)], True)
            self.bridge.actions([("up", 1), action], True)
            self.assertEqual(self.sink.packets[-1][1], 4)
            self.bridge.actions([("up", 1)], True)
            self.assertEqual(self.sink.packets[-1][1], 4)

    def test_unfocused_or_wrong_contact_has_no_click(self):
        self.bridge.actions([("down", 1, 50, 60)], False)
        self.assertNotIn(1, [p[1] for p in self.sink.packets])
        self.bridge.actions([("down", 1, 50, 60)], True)
        count = len(self.sink.packets)
        self.bridge.actions([("up", 2), ("move", 2, 0, 0)], True)
        self.assertEqual(len(self.sink.packets), count)

    def test_disconnect_never_replays_old_up(self):
        self.bridge.actions([("down", 1, 50, 60)], True)
        self.bridge.close()
        self.bridge.socket = self.sink
        count = len(self.sink.packets)
        self.bridge.actions([("up", 1)], True)
        self.assertEqual(len(self.sink.packets), count)

    def test_live_policy_and_audio_are_explicit_and_isolated(self):
        supervisor = (ROOT / "prototype/r3/supervisor.py").read_text()
        self.assertIn('touch_live=ROOT.name == "Slay the Spire for RGDSplus"', supervisor)
        self.assertIn('silent=ROOT.name != "Slay the Spire for RGDSplus"', supervisor)
        self.assertIn('default=128 if r4 else 140', supervisor)
        self.assertIn('default=32 if r4 else 64', supervisor)
        self.assertIn('default=1 if r4 else 4', supervisor)
        device = (ROOT / "prototype/r3/device.py").read_text()
        self.assertIn('sound = parser.add_mutually_exclusive_group()', device)
        self.assertIn('sound.add_argument("--silent", action="store_true")', device)
        self.assertIn("'--silent ' if args.silent else ''", device)
        agent = (ROOT / "prototype/r3/java/rgds/r3/DualAgent.java").read_text()
        self.assertNotIn("disableAudio = true;", agent)
        self.assertIn("RGDS_STS_SILENT", agent)
        self.assertIn("rgds.r3.TouchInput.poll()", agent)
        renderer = (ROOT / "prototype/r3/java/rgds/r3/DualRender.java").read_text()
        self.assertIn("hit.panel == 1 && hit.frame == frames", renderer)
        self.assertIn("hb.clickStarted = hb.clicked = false", renderer)
        self.assertIn("batch.getProjectionMatrix()).mul(batch.getTransformMatrix())", renderer)
        combat = (ROOT / "prototype/r3/java/rgds/r3/CombatTouch.java").read_text()
        self.assertIn("player.endTurnQueued || player.isEndingTurn", combat)
        self.assertIn("AbstractDungeon.actionManager.turnHasEnded", combat)
        self.assertIn("!card.canUse(player, target)", combat)
        self.assertIn("pending && presentedCard && presented == target", combat)


if __name__ == "__main__":
    unittest.main()
