"""Run on the device during a test session; injects B, L2/R2 and D-pad only."""

import fcntl
import glob
import os
from pathlib import Path
import struct
import sys
import time


APP = Path("/mnt/sdcard/Ports/SlayTheSpire")
sys.path.insert(0, str(APP))
import rgds_exit as guard


def main():
    log = Path((APP / "logs/latest-path.txt").read_text().strip())
    session = Path(str(log)[:-4])
    assert guard.game_identity(session), "no verified game session"
    assert Path(str(session) + ".exit-ready").exists()
    for proc in glob.glob("/proc/[0-9]*/comm"):
        try:
            if Path(proc).read_text().strip() == "dmenu.bin":
                state = Path(proc).with_name("stat").read_text().rsplit(")", 1)[1].split()[0]
                assert state in ("T", "t"), "system menu is still consuming input"
        except FileNotFoundError:
            pass
    matches = [Path(p) for p in glob.glob("/sys/class/input/event*/device/name")
               if Path(p).read_text().strip() == "ANBERNIC-rk3568-keys"]
    assert len(matches) == 1
    path = "/dev/input/" + matches[0].parents[1].name
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
    bits = bytearray(96)
    fcntl.ioctl(fd, 0x80604518, bits)
    assert not any(bits), "release all physical buttons before testing"

    def event(kind, code, value):
        os.write(fd, struct.pack("@llHHi", 0, 0, kind, code, value))
        os.write(fd, struct.pack("@llHHi", 0, 0, 0, 0, 0))

    def check(label, kind, code, value, expected, forbidden=None):
        offset = log.stat().st_size
        try:
            event(kind, code, value)
            time.sleep(0.25)
        finally:
            event(kind, code, 0)
        time.sleep(0.4)
        with log.open() as stream:
            stream.seek(offset)
            output = stream.read()
        assert all(text in output for text in expected), (label, output)
        assert forbidden is None or forbidden not in output, (label, output)
        print("PASS", label, flush=True)

    try:
        check("B press/release reaches game", 1, 305, 1,
              ["Button 1 DOWN", "Button 1 UP", "justPressed=true"])
        check("L2 does not navigate left", 1, 314, 1,
              ["Button 1004 DOWN", "Button 1004 UP"], "direction=")
        check("R2", 1, 315, 1, ["Button 1003 DOWN", "Button 1003 UP"])
        check("D-pad right returns to center", 3, 16, 1,
              ["direction=east", "direction=center"], "[VirtualController] Button")
        check("D-pad down does not trigger L2", 3, 17, 1,
              ["direction=south", "direction=center"], "[VirtualController] Button")
        check("D-pad left", 3, 16, -1, ["direction=west", "direction=center"])
        check("D-pad up", 3, 17, -1, ["direction=north", "direction=center"])
    finally:
        os.close(fd)
    print("Synthetic event regression passed; physical buttons still need user confirmation.")


if __name__ == "__main__":
    main()
