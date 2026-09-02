"""Live Linux commit-charge analog for this box.

Windows commit charge is RAM+pagefile. Here the pair is CommitLimit /
Committed_AS from /proc/meminfo. MemAvailable is the RAM view that hides
the bind when overcommit_ratio cuts CommitLimit well below MemTotal.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def meminfo(proc: Path | None = None) -> dict[str, int]:
    root = proc or Path("/proc")
    out: dict[str, int] = {}
    for line in (root / "meminfo").read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.split()
        n = int(parts[0])
        if len(parts) > 1 and parts[1] == "kB":
            n *= 1024
        out[key] = n
    return out


def process_count(proc: Path | None = None) -> int:
    root = proc or Path("/proc")
    return sum(1 for p in root.iterdir() if p.name.isdigit())


def snapshot(proc: Path | None = None) -> dict[str, Any]:
    m = meminfo(proc)
    committed = int(m["Committed_AS"])
    limit = int(m["CommitLimit"])
    mem_avail = int(m["MemAvailable"])
    mem_total = int(m["MemTotal"])
    headroom = limit - committed
    return {
        "MemAvailable": mem_avail,
        "MemTotal": mem_total,
        "Committed_AS": committed,
        "CommitLimit": limit,
        "commit_headroom_bytes": headroom,
        "nprocs": process_count(proc),
        "ram_hides_commit": mem_avail > headroom,
        "overcommit_memory": int(
            (proc or Path("/proc")).joinpath("sys/vm/overcommit_memory").read_text()
        )
        if (proc or Path("/proc")).joinpath("sys/vm/overcommit_memory").is_file()
        else None,
    }
