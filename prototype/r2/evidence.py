"""Summarize fetched measurements and check installed/frozen package identity."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import statistics
import zipfile

import paramiko
from PIL import Image, ImageStat

from make_package import ROOT

LOGS = ROOT / "validation/r2-probe"
PRODUCTION = {
    "rgds-input-agent.jar": "92d293fc4b671ed1c256063a8ec766e6ca7665ed20d48aeb1fd57e7953f3b292",
    "librgds-sdl.so": "5f4ff850a35f6c404406704e85e352f9241f34e3eb12b98187a80dad9a8b6620",
    "saves/IRONCLAD.autosave": "c30d66355d84647a698c33c7068d7fbfc324d332267f8cba68da564329ff888d",
}


def main():
    evidence = dict(physical_verified=False, sessions=[], captures=[], packages={})
    for path in sorted(LOGS.glob("*.jsonl")):
        events = [json.loads(line) for line in path.read_text().splitlines()]
        reports = [e for e in events if e["event"] == "performance"]
        if not reports:
            continue
        exit_event = next((e for e in events if e["event"] == "exit"), None)
        replay = next((e for e in events if e["event"] == "replay-passed"), None)
        row = dict(session=path.stem, source=reports[0]["probe"]["source"],
                   seconds=exit_event["seconds"] if exit_event else reports[-1]["seconds"],
                   graceful_result=exit_event is not None, replay=replay)
        warm = [e for e in reports if e["seconds"] >= 60]
        if warm:
            def span(values):
                return [min(values), statistics.median(values), max(values)]
            row["warm"] = dict(windows=len(warm),
                               fps_min_median_max=span([e["fps"] for e in warm]),
                               window_p95_ms_min_median_max=span([e["p95_ms"] for e in warm]),
                               max_frame_ms=max(e["max_ms"] for e in warm),
                               rss_kib_min_median_max=span([e["memory"]["VmRSS"] for e in warm]),
                               rss_first_last=[warm[0]["memory"]["VmRSS"], warm[-1]["memory"]["VmRSS"]])
        evidence["sessions"].append(row)
    for path in sorted(LOGS.glob("*.ppm")):
        with Image.open(path) as image:
            assert image.size == (2048, 768), path
            for x in (0, 1024):
                crop = image.crop((x, 0, x+1024, 768))
                assert sum(ImageStat.Stat(crop).var) > 100, path
            image.save(path.with_suffix(".png"))
        evidence["captures"].append(path.name)
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(os.environ["RGDSPLUS_SSH_HOST"], username="root",
                   password=os.environ["RGDSPLUS_SSH_PASSWORD"], timeout=10,
                   look_for_keys=False, allow_agent=False)
    sftp = client.open_sftp()
    try:
        for name in ("SlayTheSpire_R1_aim3_frozen_game-free.zip",
                     "SlayTheSpire_R2_TouchProbe_game-free.zip"):
            archive_path = ROOT / "dist" / name
            hashes = {}
            private_manifest = None
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.namelist():
                    remote = "/mnt/sdcard/" + member
                    with sftp.open(remote, "rb") as stream:
                        data = stream.read()
                    actual = hashlib.sha256(data).hexdigest()
                    expected = hashlib.sha256(archive.read(member)).hexdigest()
                    if name.startswith("SlayTheSpire_R1") and member.endswith("/manifest.json"):
                        installed = json.loads(data)
                        packaged = json.loads(archive.read(member))
                        assert installed["build"] == packaged["build"]
                        assert installed["game_assets"] is packaged["game_assets"] is False
                        for filename, checksum in packaged["files"].items():
                            assert installed["files"][filename] == checksum, filename
                        extras = set(installed["files"]) - set(packaged["files"])
                        assert extras == {"test_geometry.py", "test_input.py",
                                          "test_touch_mode.py", "replay.json"}, extras
                        for filename in extras:
                            with sftp.open(remote.rsplit("/", 1)[0] + "/" + filename, "rb") as stream:
                                checksum = hashlib.sha256(stream.read()).hexdigest()
                            assert checksum == installed["files"][filename], filename
                        private_manifest = installed
                    else:
                        assert actual == expected, remote
                    hashes[member] = actual
                    if "SlayTheSpireGeometryP1/" in member and not member.endswith("manifest.json"):
                        local = ROOT / "prototype/p1" / Path(member).name
                        assert hashlib.sha256(local.read_bytes()).hexdigest() == expected, local
            evidence["packages"][name] = dict(
                sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                installed_payload_match=True, private_validation_manifest=private_manifest,
                files=hashes)
        production = {}
        for relative, expected in PRODUCTION.items():
            with sftp.open("/mnt/sdcard/Ports/SlayTheSpire/" + relative, "rb") as stream:
                actual = hashlib.sha256(stream.read()).hexdigest()
            assert actual == expected, relative
            production[relative] = actual
        evidence["production_unchanged"] = production
        code = """
import json
from pathlib import Path
result = dict(probes=[], menus=[], touch_mode=Path('/sys/class/anbernic_misc/tpctrl').read_text().strip())
for p in Path('/proc').glob('[0-9]*/comm'):
    try:
        args = (p.parent/'cmdline').read_bytes().split(b'\\0')
        stat = (p.parent/'stat').read_text().rsplit(')',1)[1].split()
        if any(('/mnt/sdcard/Ports/' + root + '/' + name).encode() in args
               for root in ('SlayTheSpireTouchR2','SlayTheSpireGeometryP1')
               for name in ('app.py','supervisor.py')) and stat[0] != 'Z':
            result['probes'].append(int(p.parent.name))
        if p.read_text().strip() == 'dmenu.bin':
            result['menus'].append([int(p.parent.name),stat[0]])
    except FileNotFoundError:
        pass
print(json.dumps(result))
"""
        _, out, err = client.exec_command("python3 -c " + shlex.quote(code), timeout=15)
        state = json.loads(out.read())
        assert out.channel.recv_exit_status() == 0, err.read().decode()
        assert not state["probes"], state
        assert state["menus"] and all(s not in ("T", "t") for _, s in state["menus"]), state
        evidence["final_device_state"] = state
    finally:
        sftp.close()
        client.close()
    path = LOGS / "evidence-summary.json"
    path.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(dict(sessions=evidence["sessions"], captures=len(evidence["captures"]),
                          protected_files="unchanged", final_device_state=state), indent=2))
    print(path)


if __name__ == "__main__":
    main()
