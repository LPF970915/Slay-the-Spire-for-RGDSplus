"""Small, session-owned tmpfs diagnostics with bounded archival on exit."""

from pathlib import Path
import re
import shutil
import tempfile

PREFIX = "rgds-sts-r3-"
ALLOWED = re.compile(r"(state\.xml|dual-state\.xml|window-focus\.txt|touch-state\.json|"
                     r"touch-\d+\.jsonl|frames-\d+\.csv|page-result\.txt)")


def create_runtime(root, mode):
    if mode == "card":
        return root / "logs"
    return Path(tempfile.mkdtemp(prefix=PREFIX, dir="/tmp"))


def archive_runtime(root, runtime, tmp_root=Path("/tmp")):
    if runtime is None:
        return
    runtime = Path(runtime)
    if runtime == root / "logs" or not runtime.exists():
        return
    if (runtime.is_symlink() or runtime.parent.resolve() != tmp_root.resolve()
            or not re.fullmatch(PREFIX + r"[a-z0-9_]+", runtime.name)):
        raise ValueError("Refusing unowned diagnostic directory")
    sources = list(runtime.iterdir())
    for source in sources:
        if source.is_symlink() or not source.is_file():
            raise ValueError("Unexpected diagnostic entry")
        if ALLOWED.fullmatch(source.name):
            if source.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("Diagnostic file exceeded archival bound")
        elif source.name not in ("state.xml.tmp", "dual-state.xml.tmp", "window-focus.tmp",
                                  "touch-state.tmp", "touch-port.txt", "touch-port.tmp",
                                  "capture.request", "capture.pam", "page.request",
                                  "page.request.tmp", "page-result.tmp"):
            raise ValueError("Unexpected diagnostic filename: " + source.name)
    for source in sources:
        if ALLOWED.fullmatch(source.name):
            shutil.copy2(source, root / "logs" / source.name)
        source.unlink()
    runtime.rmdir()
