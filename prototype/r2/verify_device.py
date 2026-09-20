"""Finite software-injection/lifecycle checks; never certify physical touch."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import paramiko

from device import APP
from make_package import ROOT, HERE, ENTRY


def main():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("192.168.31.116", username="root",
                   password=os.environ["RGDSPLUS_SSH_PASSWORD"], timeout=10,
                   look_for_keys=False, allow_agent=False)
    output = ROOT / "validation/r2-probe"
    output.mkdir(parents=True, exist_ok=True)
    evidence = dict(source="evdev-injection", physical_verified=False, checks={})
    owned = None

    def shell(command):
        _, out, err = client.exec_command(command, timeout=30)
        text = out.read().decode() + err.read().decode()
        assert out.channel.recv_exit_status() == 0, text
        return text

    def remote(code):
        return shell("python3 -c " + shlex.quote(code))

    def action(*args):
        run = subprocess.run([sys.executable, str(HERE / "device.py"), *args],
                             capture_output=True, text=True, timeout=45)
        assert run.returncode == 0, run.stdout + run.stderr
        return run.stdout

    def snapshot():
        return json.loads(remote(f"""
import json
from pathlib import Path
result = dict(processes=[], menus=[], mode=Path('/sys/class/anbernic_misc/tpctrl').read_text().strip())
for path in Path('/proc').glob('[0-9]*/comm'):
    try:
        args = (path.parent / 'cmdline').read_bytes().split(b'\\0')
        stat = (path.parent / 'stat').read_text().rsplit(')', 1)[1].split()
        if any((root + '/' + name).encode() in args
               for root in ({APP!r}, '/mnt/sdcard/Ports/SlayTheSpireGeometryP1')
               for name in ('app.py', 'supervisor.py')) and stat[0] != 'Z':
            result['processes'].append(int(path.parent.name))
        if path.read_text().strip() == 'dmenu.bin':
            result['menus'].append([int(path.parent.name), stat[19], stat[0]])
    except FileNotFoundError:
        pass
print(json.dumps(result))
"""))

    def wait_for(predicate, seconds=12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(.25)
        raise AssertionError("Timed out waiting for R2")

    def get_state():
        return json.loads(remote(f"""
import json
from pathlib import Path
p = Path({APP + '/logs/state.json'!r})
print(p.read_text() if p.exists() else '{{}}')
"""))

    def start():
        nonlocal owned
        previous = get_state().get("session")
        action("run", "--seconds", "120", "--source", "evdev-injection", "--background")
        def ready():
            state = get_state()
            return state if (state.get("session") != previous and
                             state.get("touch", {}).get("focused")) else None
        state = wait_for(ready)
        owned = json.loads(shell(f"cat {APP}/logs/session.json"))
        return state

    def recovered(before):
        wait_for(lambda: not snapshot()["processes"])
        after = snapshot()
        assert after["mode"] == before["mode"], (before, after)
        expected = {(p, birth) for p, birth, _ in before["menus"]}
        actual = {(p, birth) for p, birth, status in after["menus"] if status not in ("T", "t")}
        assert expected <= actual, (before, after)
        return after

    try:
        before = snapshot()
        assert not before["processes"], "Close any probe before running the suite"
        assert all(s not in ("T", "t") for _, _, s in before["menus"])
        evidence["before"] = before
        initial = start()
        action("inject-grid")
        def sampled():
            state = get_state()
            return state if state["probe"]["samples"] == 27 else None
        state = wait_for(sampled)
        assert state["probe"]["measured_pass"] and not state["probe"]["physical_verified"]
        assert state["touch"]["actions"] == 54, state["touch"]
        evidence["checks"]["grid"] = state
        first = shell("/bin/sh '/mnt/sdcard/Ports/Slay the Spire P1 Geometry.sh' --seconds 1")
        second = shell("/bin/sh " + shlex.quote("/mnt/sdcard/Ports/" + ENTRY) + " --seconds 1")
        assert "P1 already running" in first and "R1 or R2 is already running" in second
        evidence["checks"]["mutual_exclusion"] = [first, second]
        action("key", "--code", "308", "--hold", ".06")
        wait_for(lambda: get_state()["probe"]["mode"] == "drag")
        action("freeze")
        action("key", "--code", "310", "--hold", "1.8")
        evidence["checks"]["frozen_exit"] = recovered(before)
        evidence["checks"]["frozen_log"] = shell(f"cat {APP}/logs/latest.log")
        assert "independent exit requested" in evidence["checks"]["frozen_log"]
        evidence["checks"]["frozen_session"] = initial["session"]
        owned = None
        initial = start()
        action("crash")
        evidence["checks"]["supervisor_recovery"] = recovered(before)
        evidence["checks"]["recovery_log"] = shell(f"cat {APP}/logs/latest.log")
        assert "[touch-mode] restored=" in evidence["checks"]["recovery_log"]
        evidence["checks"]["recovery_session"] = initial["session"]
        owned = None
        initial = start()
        action("key", "--code", "310", "--hold", "1.8")
        evidence["checks"]["normal_exit"] = recovered(before)
        result = json.loads(shell(f"cat {APP}/logs/{initial['session']}-result.json"))
        assert result["probe"]["physical_verified"] is False
        evidence["checks"]["normal_result"] = result
        evidence["checks"]["normal_log"] = shell(f"cat {APP}/logs/latest.log")
        assert "app_exit=0" in evidence["checks"]["normal_log"]
        owned = None
        evidence["passed"] = True
        action("fetch")
    finally:
        if owned:
            # Clean up only the supervisor identity launched by this suite.
            remote(f"""
import signal, sys
sys.path.insert(0, {APP!r})
from supervisor import send
send({owned['owner']}, {owned['birth']!r}, signal.SIGTERM)
""")
            wait_for(lambda: not snapshot()["processes"])
        path = output / ("lifecycle-" + str(time.time_ns()) + ".json")
        path.write_text(json.dumps(evidence, indent=2))
        client.close()
    print(json.dumps(evidence, indent=2))
    print(path)


if __name__ == "__main__":
    main()
