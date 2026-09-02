"""Load-shed guards. CommitChargeGuard never consults working_set."""
from __future__ import annotations

from commit import Sample

DEFAULT_SHED_RATIO = 0.80


class CommitChargeGuard:
    """Sheds when commit_charge / commit_limit crosses the ratio.

    Does not read working_set, ram_total, or any RSS analog. A working-set
    reading is silent in the Windows Event 2004 / commit-exhaustion state.
    """

    def __init__(self, shed_ratio: float = DEFAULT_SHED_RATIO) -> None:
        if not 0 < shed_ratio < 1:
            raise ValueError("shed_ratio must be in (0, 1)")
        self.shed_ratio = shed_ratio

    def should_shed(self, snap: Sample) -> bool:
        if snap.commit_limit <= 0:
            return True
        commit_ratio = snap.commit_charge / snap.commit_limit
        return commit_ratio >= self.shed_ratio


class WorkingSetGuard:
    """Control: RAM-percent / working-set guard. Silent under commit pressure."""

    def __init__(self, shed_ratio: float = DEFAULT_SHED_RATIO) -> None:
        if not 0 < shed_ratio < 1:
            raise ValueError("shed_ratio must be in (0, 1)")
        self.shed_ratio = shed_ratio

    def should_shed(self, snap: Sample) -> bool:
        if snap.ram_total <= 0:
            return True
        return snap.working_set / snap.ram_total >= self.shed_ratio
