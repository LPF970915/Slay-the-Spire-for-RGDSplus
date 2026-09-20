"""Session-scoped firmware touch mode, matching the Balatro launch contract."""

from pathlib import Path

CONTROL = Path("/sys/class/anbernic_misc/tpctrl")


def read_mode(path=CONTROL, log=print):
    try:
        value = path.read_text().strip()
        if value in ("0", "1"):
            return value
        log(f"[touch-mode] unknown value {value!r}; unchanged")
    except OSError as error:
        log(f"[touch-mode] unavailable: {error}")
    return None


def enable_mode(previous, path=CONTROL, log=print):
    if previous not in ("0", "1"):
        return False
    try:
        # Repeat Balatro's explicit activation write even if readback is zero.
        path.write_text("0\n")
        current = path.read_text().strip()
        log(f"[touch-mode] before={previous} requested=0 active={current}")
        return current == "0"
    except OSError as error:
        log(f"[touch-mode] enable failed: {error}")
        return False


def restore_mode(previous, path=CONTROL, log=print):
    if previous not in ("0", "1"):
        return False
    try:
        current = path.read_text().strip()
        if current != "0":
            log(f"[touch-mode] restore skipped: current={current!r}")
            return False
        path.write_text(previous + "\n")
        log(f"[touch-mode] restored={path.read_text().strip()}")
        return True
    except OSError as error:
        log(f"[touch-mode] restore failed: {error}")
        return False
