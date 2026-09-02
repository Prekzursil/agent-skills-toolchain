"""Memory snapshot helpers for the commit-charge guard.

The guard's headline cost is *commit charge* (``Committed_AS`` against
``CommitLimit`` on Linux; ``Memory\\Committed Bytes`` against
``Memory\\Commit Limit`` on Windows) plus the pagefile/swap size, not
RAM-percent.  RAM-percent is kept on the snapshot only as a control
comparator: the estate's freeze mode was commit exhaustion, which RAM-percent
does not see.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

GiB = 1024**3

#: ``/proc/meminfo`` keys read for the commit-charge counter.
COMMIT_CHARGE_KEY = "Committed_AS"
COMMIT_LIMIT_KEY = "CommitLimit"
#: Linux analogue of the Windows pagefile size.
PAGEFILE_KEY = "SwapTotal"
#: RAM-percent control fields (a different instrument than commit charge).
RAM_TOTAL_KEY = "MemTotal"
RAM_AVAILABLE_KEY = "MemAvailable"

#: Order in which ``read_live`` reads the counters; recorded verbatim.
LIVE_FIELDS: tuple[str, ...] = (
    COMMIT_CHARGE_KEY,
    COMMIT_LIMIT_KEY,
    RAM_TOTAL_KEY,
    RAM_AVAILABLE_KEY,
    PAGEFILE_KEY,
)

#: Windows performance counters equivalent to the Linux keys above.
WINDOWS_COUNTERS: tuple[str, ...] = (
    "Memory\\Committed Bytes",
    "Memory\\Commit Limit",
)

PROC_MEMINFO = Path("/proc/meminfo")
SOURCE_PROC_MEMINFO = "proc-meminfo"
SOURCE_SYNTHETIC = "synthetic"

_UNIT_BYTES: Dict[str, int] = {"": 1, "b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}


@dataclass
class MemorySnapshot:
    committed_bytes: int
    commit_limit_bytes: int
    ram_used_bytes: int
    ram_total_bytes: int
    pagefile_bytes: int
    label: str = ""
    source: str = SOURCE_SYNTHETIC
    fields_read: List[str] = field(default_factory=list)
    host: str = ""

    @property
    def commit_ratio(self) -> float:
        if self.commit_limit_bytes <= 0:
            return 0.0
        return self.committed_bytes / self.commit_limit_bytes

    @property
    def ram_percent(self) -> float:
        if self.ram_total_bytes <= 0:
            return 0.0
        return 100.0 * self.ram_used_bytes / self.ram_total_bytes

    @property
    def commit_headroom_bytes(self) -> int:
        return max(0, self.commit_limit_bytes - self.committed_bytes)

    def as_dict(self) -> Dict[str, object]:
        """Flat, JSON-serialisable view with derived ratios rounded for receipts."""
        return {
            "commit_headroom_bytes": self.commit_headroom_bytes,
            "commit_limit_bytes": self.commit_limit_bytes,
            "commit_ratio": round(self.commit_ratio, 6),
            "committed_bytes": self.committed_bytes,
            "fields_read": list(self.fields_read),
            "host": self.host,
            "label": self.label,
            "pagefile_bytes": self.pagefile_bytes,
            "ram_percent": round(self.ram_percent, 4),
            "ram_total_bytes": self.ram_total_bytes,
            "ram_used_bytes": self.ram_used_bytes,
            "source": self.source,
            "windows_counters": list(WINDOWS_COUNTERS),
        }


def synthetic_snapshot(
    *,
    committed_bytes: int,
    commit_limit_bytes: int,
    ram_used_bytes: int,
    ram_total_bytes: int,
    pagefile_bytes: int,
    label: str = "",
) -> MemorySnapshot:
    return MemorySnapshot(
        committed_bytes=committed_bytes,
        commit_limit_bytes=commit_limit_bytes,
        ram_used_bytes=ram_used_bytes,
        ram_total_bytes=ram_total_bytes,
        pagefile_bytes=pagefile_bytes,
        label=label,
        source=SOURCE_SYNTHETIC,
        fields_read=[],
        host=platform.system().lower(),
    )


def parse_meminfo(text: str) -> Dict[str, int]:
    """Parse ``/proc/meminfo`` text into ``{key: bytes}``.

    Lines look like ``Committed_AS:    5906120 kB``; a missing unit means bytes
    (``HugePages_Total`` and friends).  Malformed lines are skipped rather than
    guessed.
    """
    out: Dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        parts = rest.split()
        if not parts or not parts[0].lstrip("-").isdigit():
            continue
        unit = parts[1].lower() if len(parts) > 1 else ""
        if unit not in _UNIT_BYTES:
            continue
        out[key.strip()] = int(parts[0]) * _UNIT_BYTES[unit]
    return out


def snapshot_from_meminfo(
    values: Dict[str, int], *, label: str = "live:/proc/meminfo"
) -> MemorySnapshot:
    """Build a snapshot from parsed meminfo values, recording which keys were read."""
    fields_read = [key for key in LIVE_FIELDS if key in values]
    ram_total = values.get(RAM_TOTAL_KEY, 0)
    ram_available = values.get(RAM_AVAILABLE_KEY, 0)
    return MemorySnapshot(
        committed_bytes=values.get(COMMIT_CHARGE_KEY, 0),
        commit_limit_bytes=values.get(COMMIT_LIMIT_KEY, 0),
        ram_used_bytes=max(0, ram_total - ram_available),
        ram_total_bytes=ram_total,
        pagefile_bytes=values.get(PAGEFILE_KEY, 0),
        label=label,
        source=SOURCE_PROC_MEMINFO,
        fields_read=fields_read,
        host=platform.system().lower(),
    )


def read_live(meminfo_path: Optional[Path] = None) -> MemorySnapshot:
    """Read the live commit charge, commit limit and swap size from ``/proc/meminfo``.

    Raises ``FileNotFoundError`` where ``/proc/meminfo`` does not exist (a
    non-Linux host); callers that want the Windows counters must read
    ``WINDOWS_COUNTERS`` through their own instrument, this module never
    fabricates a value.
    """
    path = Path(meminfo_path) if meminfo_path is not None else PROC_MEMINFO
    text = path.read_text(encoding="utf-8", errors="replace")
    return snapshot_from_meminfo(parse_meminfo(text), label=f"live:{path}")
