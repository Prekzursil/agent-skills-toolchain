"""Memory snapshot helpers for the commit-charge guard."""
from __future__ import annotations

from dataclasses import dataclass

GiB = 1024**3


@dataclass
class MemorySnapshot:
    committed_bytes: int
    commit_limit_bytes: int
    ram_used_bytes: int
    ram_total_bytes: int
    pagefile_bytes: int
    label: str = ""

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
    )
