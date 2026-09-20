"""Static fail-closed checks for the isolated native UI milestone."""

import ast
from pathlib import Path
import zipfile
from test_touch_contract import calls, functions

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "prototype/r3"


def main():
    fn = functions(HERE/"supervisor.py")
    main_fn, recover = fn["main"], fn["recover"]
    read = calls(main_fn, "read_mode")[0].lineno
    enable = calls(main_fn, "enable_mode")[0].lineno
    assert any(read < c.lineno < enable for c in calls(main_fn, "persist"))
    spawns = sorted(calls(main_fn, "Popen"), key=lambda n: n.lineno)
    assert spawns[0].lineno < read < enable < spawns[1].lineno < spawns[2].lineno
    assert "pass_fds" in [k.arg for k in spawns[0].keywords]
    assert "pass_fds" not in [k.arg for k in spawns[2].keywords]
    assert calls(recover, "restore_mode")
    assert calls(recover, "stop_runtime")[0].lineno < calls(recover, "restore_mode")[0].lineno
    finalizers = [n for n in ast.walk(main_fn) if isinstance(n, ast.Try) and n.finalbody]
    assert any(any(calls(n, "restore_mode") for n in f.finalbody) for f in finalizers)
    bridge = ast.parse((HERE/"touch_bridge.py").read_text())
    for call in ("set_focus", "cancel_touch", "diagnostics"):
        assert calls(bridge, call)
    assert min(c.lineno for c in calls(bridge, "cancel_touch")) < calls(bridge, "set_focus")[0].lineno
    assert "capture-only" in (HERE/"touch_bridge.py").read_text()
    assert "heartbeat.stat().st_mtime" not in (HERE/"touch_bridge.py").read_text()
    assert "SDL_PumpEvents" in (HERE/"dual_sdl.c").read_text()
    assert "syscall(SYS_gettid) == video_thread" in (HERE/"dual_sdl.c").read_text()
    renderer = (HERE/"java/rgds/r3/DualRender.java").read_text()
    assert "glReadPixels" not in renderer
    assert "renderCombatRoomBg(" not in renderer
    assert ".update(" not in renderer
    assert "new Matrix4(baseProjection).mul(transform)" in renderer
    with zipfile.ZipFile(HERE/"build/rgds-dual-r3.jar") as jar:
        assert all(n.startswith(("rgds/", "META-INF/")) for n in jar.namelist())
    print("R3 lifecycle, input capture, single-update routing and asset-free agent checks passed")


if __name__ == "__main__":
    main()
