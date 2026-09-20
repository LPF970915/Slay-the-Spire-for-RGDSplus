import unittest

from device_input import Touch, dispatch
from geometry import Model
from test_geometry import aim


def contact(touch, slot, uid, x=512, y=590):
    events = []
    for event in ((3, 47, slot), (3, 57, uid), (3, 53, x), (3, 54, y), (0, 0, 0)):
        events.extend(touch.feed(*event))
    return events


class InputTests(unittest.TestCase):
    def test_single_finger_and_release(self):
        touch = Touch()
        actions = contact(touch, 0, 123)
        token = actions[0][1]
        self.assertEqual(actions, [("down", token, 512, 590)])
        self.assertEqual(contact(touch, 0, 123, 512, 300),
                         [("move", token, 512, 300)])
        self.assertEqual(contact(touch, 0, -1, 512, 300), [("up", token)])
        self.assertEqual(contact(touch, 0, -1), [])

    def test_second_finger_drains(self):
        touch = Touch()
        contact(touch, 0, 1)
        self.assertEqual(contact(touch, 1, 2), [("cancel", "second-finger")])
        self.assertEqual(contact(touch, 0, -1), [])
        self.assertEqual(contact(touch, 1, -1), [])
        self.assertEqual(contact(touch, 0, 3)[0][0], "down")

    def test_dropped_requires_resync(self):
        touch = Touch()
        contact(touch, 0, 1)
        self.assertEqual(touch.feed(0, 3, 0), [("cancel", "syn-dropped")])
        self.assertEqual(touch.feed(3, 57, -1), [])
        self.assertEqual(touch.feed(0, 0, 0), [("resync",)])
        self.assertTrue(touch.blocked)

    def test_contact_replaced(self):
        touch = Touch()
        contact(touch, 0, 1)
        self.assertEqual(contact(touch, 0, 2), [("cancel", "contact-replaced")])

    def test_axis_calibration(self):
        touch = Touch(4095, 4095)
        point = contact(touch, 0, 1, 4095, 4095)[0]
        self.assertEqual(point[2:], (1024, 768))

    def test_b_wins_a_and_release(self):
        for actions in ([("button", "a"), ("button", "b")],
                        [("up", 11), ("button", "b")]):
            m = Model()
            aim(m)
            m.displayed()
            dispatch(m, actions)
            self.assertEqual(m.commits, 0)

    def test_final_release_coordinates_are_not_stale(self):
        touch = Touch()
        m = Model()
        dispatch(m, contact(touch, 0, 1))
        dispatch(m, contact(touch, 0, 1, 512, 273))
        m.displayed()
        dispatch(m, contact(touch, 0, -1, 10, 200))
        self.assertEqual(m.commits, 0)

    def test_reconnected_device_has_new_gesture_identity(self):
        old = contact(Touch(), 0, 1)[0][1]
        new = contact(Touch(), 0, 1)[0][1]
        self.assertNotEqual(old, new)


if __name__ == "__main__":
    unittest.main()
