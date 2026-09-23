"""Deploy the game-free P0 adapter and optionally a local user JAR."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
from pathlib import Path
import shlex
import time
import zipfile

import paramiko


ROOT = Path(__file__).resolve().parents[1]
REMOTE_PORTS = "/mnt/mmc/Ports"
REMOTE_APP = REMOTE_PORTS + "/SlayTheSpire"
REMOTE_ENTRY = REMOTE_PORTS + "/Slay the Spire for RGDSplus.sh"
ALLOWED_GAME_FILE = "desktop-1.0.jar"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def upload(sftp, local: Path, remote: str) -> None:
    with local.open("rb") as source, sftp.open(remote, "wb", bufsize=0) as target:
        while chunk := source.read(32768):
            target.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--package",
        type=Path,
        default=ROOT / "dist/SlayTheSpire_RGDSplus_P0_game-free.zip",
    )
    parser.add_argument("--game", type=Path)
    parser.add_argument("--host", default=os.getenv("RGDSPLUS_SSH_HOST"))
    parser.add_argument("--user", default="root")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument(
        "--remote-ports", choices=("/mnt/mmc/Ports", "/mnt/sdcard/Ports"),
        default="/mnt/sdcard/Ports",
        help="target card (default: card 2)",
    )
    args = parser.parse_args()
    global REMOTE_PORTS, REMOTE_APP, REMOTE_ENTRY
    REMOTE_PORTS = args.remote_ports
    REMOTE_APP = REMOTE_PORTS + "/SlayTheSpire"
    REMOTE_ENTRY = REMOTE_PORTS + "/Slay the Spire for RGDSplus.sh"

    package = args.package.resolve()
    if not package.is_file():
        raise SystemExit(f"missing package: {package}")
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert "Ports/SlayTheSpire/launch.sh" in names
        assert "Ports/Slay the Spire for RGDSplus.sh" in names
        assert not any(
            name.lower().endswith(("desktop-1.0.jar", "slaythespire.exe", ".love"))
            for name in names
        )
    game = args.game.resolve() if args.game else None
    if game is not None:
        if game.name != ALLOWED_GAME_FILE:
            raise SystemExit(f"--game must point to {ALLOWED_GAME_FILE}")
        if not game.is_file():
            raise SystemExit(f"missing game file: {game}")
        game_sha = digest(game)
        print(f"private game sha256={game_sha}")

    password = os.getenv("RGDSPLUS_SSH_PASSWORD") or getpass.getpass(
        f"Password for {args.user}@{args.host}: "
    )
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username=args.user,
        password=password,
        timeout=12,
        auth_timeout=12,
        look_for_keys=False,
        allow_agent=False,
    )
    stage = f"{REMOTE_PORTS}/.slaythespire-p0-stage-{time.time_ns()}"

    def shell(command: str) -> str:
        _, stdout, stderr = client.exec_command("set -e\n" + command, timeout=120)
        output = stdout.read().decode("utf-8", "replace")
        errors = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        if rc:
            raise RuntimeError(f"remote rc={rc}\n{output}{errors}")
        return output + errors

    try:
        with client.open_sftp() as sftp:
            sftp.get_channel().settimeout(120)
            shell(
                ("mountpoint -q /mnt/sdcard\n" if REMOTE_PORTS.startswith("/mnt/sdcard/") else "")
                +
                f"mkdir -p {shlex.quote(stage)}\n"
                "if ps -eo pid=,comm=,args= | awk "
                "'$2 ~ /^java/ && ($0 ~ /SlayTheSpire|desktop-1[.]0[.]jar/) "
                "{ found=1 } END { exit !found }'; then "
                "echo 'game is running'; exit 1; fi"
            )
            upload(sftp, package, stage + "/package.zip")
            shell(
                f"unzip -oq {shlex.quote(stage + '/package.zip')} "
                f"-d {shlex.quote(stage + '/unpacked')}"
            )
            release_root = stage + "/unpacked/Ports"
            release_files = [
                name
                for name in names
                if name.startswith("Ports/") and not name.endswith("/")
            ]
            for name in sorted(release_files):
                relative = name.removeprefix("Ports/")
                remote = REMOTE_PORTS + "/" + relative
                staged = release_root + "/" + relative
                shell(
                    f"mkdir -p {shlex.quote(remote.rsplit('/', 1)[0])}\n"
                    f"mv {shlex.quote(staged)} {shlex.quote(remote)}"
                )
            shell(
                f"chmod +x {shlex.quote(REMOTE_APP + '/launch.sh')} "
                f"{shlex.quote(REMOTE_APP + '/patch_safe.sh')} "
                f"{shlex.quote(REMOTE_ENTRY)}"
            )
            if game is not None:
                upload(sftp, game, REMOTE_APP + "/" + ALLOWED_GAME_FILE + ".new")
                shell(
                    f"mv {shlex.quote(REMOTE_APP + '/' + ALLOWED_GAME_FILE + '.new')} "
                    f"{shlex.quote(REMOTE_APP + '/' + ALLOWED_GAME_FILE)}"
                )
                remote_sha = shell(
                    f"sha256sum {shlex.quote(REMOTE_APP + '/' + ALLOWED_GAME_FILE)}"
                ).split()[0]
                if remote_sha != game_sha:
                    raise RuntimeError("remote game hash mismatch")
            if args.launch:
                shell(
                    f"nohup /bin/bash {shlex.quote(REMOTE_ENTRY)} "
                    f"> {shlex.quote(REMOTE_APP + '/logs/deploy-start.log')} "
                    "< /dev/null &"
                )
        print(f"deployed adapter to {REMOTE_APP}")
        if game is not None:
            print("uploaded the private game JAR separately; it is not in the package")
        if args.launch:
            print(f"launch requested; inspect {REMOTE_APP}/logs/latest-path.txt")
    finally:
        try:
            shell(f"rm -rf {shlex.quote(stage)}")
        finally:
            client.close()


if __name__ == "__main__":
    main()
