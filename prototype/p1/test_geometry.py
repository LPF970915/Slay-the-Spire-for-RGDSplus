import math
import unittest

from geometry import (Model, CARD_X, CARD_Y, H, W, Target, angular_interval, OUTER_SNAP,
                      arrow_segments, clip_segment, pick)


def aim(model, uid=11, card=1, target=0):
    x, y = CARD_X[card], CARD_Y
    model.down(uid, x, y)
    t = model.targets[target]
    model.move(uid, x + (t.x - x) * 0.3,
               y + (t.y - (y + H + model.gap)) * 0.3)


class GeometryTests(unittest.TestCase):
    def test_all_origins_and_scenes(self):
        for scene in (0, 1, 2, 4):
            for card in range(3):
                m = Model()
                m.change_scene(scene)
                for index in range(len(m.targets)):
                    with self.subTest(scene=scene, card=card, target=index):
                        aim(m, card=card, target=index)
                        self.assertEqual(m.target, m.targets[index].uid)
                        m.displayed()
                        m.up(11)
                        self.assertEqual(m.commits, index + 1)

    def test_ambiguity_no_first_item(self):
        targets = [Target("a", 492, 350), Target("b", 532, 350)]
        for order in (targets, list(reversed(targets))):
            self.assertEqual(pick((512, 1400), (512, 1000), order),
                             (None, "ambiguous"))

    def test_no_auto_snap(self):
        self.assertEqual(pick((512, 1400), (1000, 1100),
                              [Target("a", 512, 350)])[0], None)

    def test_upward_threshold(self):
        m = Model()
        m.down(1, 512, 590)
        m.move(1, 512, 544)
        m.displayed()
        m.up(1)
        self.assertEqual(m.commits, 0)

    def test_hysteresis_bounded(self):
        target = Target("a", 512, 350)
        origin = (512, 1400)
        _, hi = angular_interval(origin, target)
        pointer = (512 + math.tan(hi + 0.08) * 300, 1100)
        self.assertEqual(pick(origin, pointer, [target])[0], "a")
        self.assertEqual(pick(origin, pointer, [target], "a")[0], "a")
        pointer = (512 + math.tan(hi + OUTER_SNAP + 0.01) * 300, 1100)
        self.assertIsNone(pick(origin, pointer, [target], "a")[0])

    def test_display_before_commit(self):
        m = Model()
        aim(m)
        m.up(11)
        self.assertEqual(m.commits, 0)
        self.assertTrue(m.release_pending)
        m.displayed()
        self.assertEqual(m.commits, 1)
        aim(m, 12)
        m.displayed()
        m.up(12)
        m.up(12)
        self.assertEqual(m.commits, 2)

    def test_stale_up_and_takeover(self):
        m = Model()
        aim(m, 7)
        m.displayed()
        m.button("right")
        m.up(7)
        self.assertEqual(m.owner, "pad")
        self.assertEqual(m.commits, 0)
        m.displayed()
        m.button("a")
        self.assertEqual(m.commits, 1)
        aim(m, 8)
        m.up(7)
        self.assertEqual(m.gesture, 8)

    def test_target_removed(self):
        m = Model()
        aim(m)
        m.displayed()
        m.remove_target()
        m.up(11)
        self.assertEqual(m.commits, 0)
        self.assertIsNone(m.owner)

    def test_cancel_and_scene_generation(self):
        for reason in ("focus-loss", "syn-dropped", "second-finger", "disconnect"):
            m = Model()
            aim(m)
            m.displayed()
            m.cancel(reason)
            m.up(11)
            self.assertEqual(m.commits, 0)
        m = Model()
        aim(m)
        old = m.target
        m.change_scene(m.scene)
        self.assertNotIn(old, [t.uid for t in m.targets])

    def test_drag_back_and_edge(self):
        for point in ((512, 575), (512, 1), (0, 400)):
            m = Model()
            aim(m)
            m.move(11, *point)
            m.up(11)
            self.assertIsNone(m.owner)
            self.assertEqual(m.commits, 0)

    def test_pad_fallback_in_ambiguous_scene(self):
        m = Model()
        m.change_scene(3)
        m.button("a")
        m.button("right")
        self.assertEqual(m.target, m.targets[1].uid)
        m.displayed()
        m.button("a")
        self.assertEqual(m.commits, 1)

    def test_fixed_anchor(self):
        m = Model()
        m.down(1, 470, 620)
        m.move(1, 460, 400)
        self.assertEqual(m.origin, (470, 620 + H + m.gap))

    def test_gap_cancel(self):
        m = Model()
        aim(m)
        m.change_gap(16)
        m.up(11)
        self.assertEqual(m.commits, 0)
        self.assertEqual(m.gap, 64)

    def test_clip_and_arrow(self):
        self.assertEqual(clip_segment((50, 1000), (50, 0), 0, H),
                         ((50, 768), (50, 0)))
        for gap in (0, 48, 160):
            for phase in (0, 8, 31):
                screens = arrow_segments((160, H + gap + 590), (904, 350), gap, phase)
                self.assertTrue(all(screens))
                for segments in screens:
                    for a, b in segments:
                        for x, y in (a, b):
                            self.assertTrue(-0.001 <= x <= W + 0.001)
                            self.assertTrue(-0.001 <= y <= H + 0.001)

    def test_arrow_tip_does_not_cover_target_label(self):
        m = Model()
        aim(m)
        t = m.targets[0]
        x, y = m.arrow_tip()
        self.assertTrue(abs(x - t.x) > t.w / 2 or abs(y - t.y) > t.h / 2)
        ox, oy = m.origin
        self.assertAlmostEqual((x - ox) * (t.y - oy), (y - oy) * (t.x - ox))

    def test_top_edge_keeps_highlight_until_release(self):
        m = Model()
        aim(m, target=2)
        for y in (240, 100, 24, 8, 1, 0):
            m.move(11, 512, y)
            self.assertEqual(m.target, m.targets[2].uid)
            self.assertIsNotNone(m.direction_tip())
        m.displayed()
        m.up(11)
        self.assertEqual(m.commits, 0)
        self.assertEqual(m.status, "edge-release")

    def test_large_upward_drag_from_every_card(self):
        for card, x in enumerate(CARD_X):
            for index in range(5):
                m = Model()
                aim(m, card=card, target=index)
                target = m.targets[index]
                for y in (200, 80, 8):
                    px = x + (target.x - x) * (CARD_Y - y) / (CARD_Y + H + m.gap - target.y)
                    m.move(11, px, y)
                    self.assertEqual(m.target, target.uid)
                    m.displayed()
                m.up(11)
                self.assertEqual(m.commits, 1)

    def test_between_enemy_sectors_stays_selected(self):
        targets = [Target("a", 316, 350), Target("b", 512, 350)]
        origin = (512, 1400)
        angle_a = math.atan2(316 - 512, 1050)
        angle = angle_a * 0.45
        pointer = (512 + math.tan(angle) * 300, 1100)
        self.assertEqual(pick(origin, pointer, targets, "a")[0], "a")
        self.assertEqual(pick(origin, pointer, targets)[0], "b")

    def test_neutral_direction_remains_for_no_target_and_overlap(self):
        m = Model()
        m.change_scene(0)
        m.down(1, 512, 590)
        m.move(1, 990, 480)
        self.assertIsNone(m.target)
        self.assertIsNotNone(m.direction_tip())
        m.cancel()
        m.change_scene(3)
        m.down(2, 512, 590)
        m.move(2, 512, 200)
        self.assertEqual(m.status, "ambiguous")
        self.assertIsNotNone(m.direction_tip())
        m.up(2)
        m.displayed()
        self.assertEqual(m.commits, 0)

    def test_quick_release_never_retargets_and_can_cancel(self):
        for action in ("b", "y", "r"):
            m = Model()
            aim(m, target=2)
            m.up(11)
            self.assertTrue(m.release_pending)
            m.button(action)
            m.displayed()
            self.assertEqual(m.commits, 0)
        m = Model()
        aim(m, target=2)
        original = m.target
        m.up(11)
        m.move(11, 900, 100)
        self.assertEqual(m.target, original)
        m.displayed()
        m.displayed()
        self.assertEqual(m.commits, 1)
        self.assertEqual(m.last_commit["target"], original)


if __name__ == "__main__":
    unittest.main()
