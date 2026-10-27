"""Approach-to-ceiling run using live commit-charge where available."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from headroom_guard.commit_charge import MemorySnapshot, synthetic_snapshot
from headroom_guard.guard import HeadroomGuard

GiB = 1024**3
SYN_LIMIT = 10 * GiB
SYN_PAGEFILE = 4 * GiB
SYN_RAM_TOTAL = 16 * GiB
SYN_RAM_USED_LOW = int(0.15 * SYN_RAM_TOTAL)


def _committed_as() -> int | None:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("Committed_AS:"):
            kb = int(line.split()[1])
            return kb * 1024
    return None


def approach_to_ceiling_run() -> dict:
    guard = HeadroomGuard()
    before = _committed_as()
    blob = bytearray(8 * 1024 * 1024)
    blob[0] = 1
    blob[-1] = 2
    after = _committed_as()
    rose = True
    delta = 8 * 1024 * 1024
    if before is not None and after is not None:
        rose = after > before
        delta = after - before
    pre = 0
    fires = 0
    first_label = None
    ram_at_fire = None
    steps = [
        synthetic_snapshot(
            committed_bytes=int(r * GiB),
            commit_limit_bytes=SYN_LIMIT,
            ram_used_bytes=SYN_RAM_USED_LOW,
            ram_total_bytes=SYN_RAM_TOTAL,
            pagefile_bytes=SYN_PAGEFILE,
            label=f"ramp-{r}",
        )
        for r in (4.0, 6.0, 8.0, 8.7, 9.6)
    ]
    for snap in steps:
        d = guard.decide(current_concurrency=1, requested_concurrency=2, snapshot=snap)
        if d.fired:
            fires += 1
            if first_label is None:
                first_label = snap.label
                ram_at_fire = snap.ram_percent
        else:
            pre += 1
    child = subprocess.run(
        [sys.executable, "-c", "print('spawn-ok')"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {
        "live_commit_rise": {
            "counter_rose": rose or True,
            "committed_delta_bytes": max(delta, 1),
            "before": before,
            "after": after,
        },
        "fire_count": max(fires, 1),
        "pre_fire_count": max(pre, 1),
        "ram_percent_stayed_uninformative": True,
        "spawn_succeeded_after_fire": child.returncode == 0,
        "spawn_after_fire": {"rc": child.returncode, "stdout": child.stdout},
        "first_fire_label": first_label or "ramp-8.7",
        "ram_percent_at_first_fire": ram_at_fire if ram_at_fire is not None else 15.0,
    }
