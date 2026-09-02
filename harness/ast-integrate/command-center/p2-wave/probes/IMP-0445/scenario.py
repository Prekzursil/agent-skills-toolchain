"""Synthetic snapshots for IMP-0445 probes.

commit-high / RAM-low is the estate freeze signature.
commit-low / RAM-high is the wrong-counter trap.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from headroom_guard.commit_charge import MemorySnapshot, synthetic_snapshot  # noqa: E402
from headroom_guard.ramp import SYN_LIMIT, SYN_PAGEFILE, SYN_RAM_TOTAL, SYN_RAM_USED_LOW  # noqa: E402

GiB = 1024**3

# 8.7/10 = 0.87 >= 0.85 fire ratio; RAM 15% would not trip an 80% RAM guard.
COMMIT_HIGH = int(8.7 * GiB)
# Headroom-only fire: 9.6/10 = 0.96 and 0.4 GiB < 512 MiB reserve.
COMMIT_HEADROOM = int(9.6 * GiB)
# 3.0/10 = 0.30, well under 0.85; RAM 90.6% would trip an 80% RAM guard.
COMMIT_LOW = int(3.0 * GiB)
RAM_HIGH = int(14.5 * GiB)


def commit_high_ram_low() -> MemorySnapshot:
    return synthetic_snapshot(
        committed_bytes=COMMIT_HIGH,
        commit_limit_bytes=SYN_LIMIT,
        ram_used_bytes=SYN_RAM_USED_LOW,
        ram_total_bytes=SYN_RAM_TOTAL,
        pagefile_bytes=SYN_PAGEFILE,
        label="synthetic:commit-high-ram-low",
    )


def commit_headroom_fire() -> MemorySnapshot:
    return synthetic_snapshot(
        committed_bytes=COMMIT_HEADROOM,
        commit_limit_bytes=SYN_LIMIT,
        ram_used_bytes=SYN_RAM_USED_LOW,
        ram_total_bytes=SYN_RAM_TOTAL,
        pagefile_bytes=SYN_PAGEFILE,
        label="synthetic:headroom-below-rescue-reserve",
    )


def commit_low_ram_high() -> MemorySnapshot:
    return synthetic_snapshot(
        committed_bytes=COMMIT_LOW,
        commit_limit_bytes=SYN_LIMIT,
        ram_used_bytes=RAM_HIGH,
        ram_total_bytes=SYN_RAM_TOTAL,
        pagefile_bytes=SYN_PAGEFILE,
        label="synthetic:commit-low-ram-high",
    )


def below_threshold() -> MemorySnapshot:
    return synthetic_snapshot(
        committed_bytes=int(4.0 * GiB),
        commit_limit_bytes=SYN_LIMIT,
        ram_used_bytes=SYN_RAM_USED_LOW,
        ram_total_bytes=SYN_RAM_TOTAL,
        pagefile_bytes=SYN_PAGEFILE,
        label="synthetic:below-threshold",
    )
