"""Count Linux processes whose /proc cmdline contains a needle."""

from __future__ import annotations

from pathlib import Path


def cmdline_pids(needle: str, *, exclude_pids: set[int] | None = None) -> list[int]:
    if not needle:
        raise ValueError("empty process-table needle")
    exclude = exclude_pids or set()
    found: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        raise FileNotFoundError("/proc is required for process-table measurement")
    for entry in proc.iterdir():
        name = entry.name
        if not name.isdigit():
            continue
        pid = int(name)
        if pid in exclude:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        cmd = raw.replace(b"\x00", b" ").decode("utf-8", "replace")
        if needle in cmd:
            found.append(pid)
    return found


def count_cmdline(needle: str, *, exclude_pids: set[int] | None = None) -> int:
    return len(cmdline_pids(needle, exclude_pids=exclude_pids))
