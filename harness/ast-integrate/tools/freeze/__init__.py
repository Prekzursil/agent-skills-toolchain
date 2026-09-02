"""Phase-0 freeze protocol (CC-0010).

The single submodule ``protocol`` snapshots the nine estate classes, marks
working-tree measurements SAMPLE, and emits BASELINE only when two independent
quiescence signals agree inside an unwritten git worktree. Its public surface
is re-exported here so ``tools.freeze`` and ``tools.freeze.protocol`` agree.
"""
from __future__ import annotations

from .protocol import (
    NINE_CLASSES,
    PROGRAM_ANCHOR_PREFIX,
    freeze_live_worktree,
    run_adversarial_control,
    run_quiescent_baseline_control,
    run_rollback_rehearsal,
)

__all__ = [
    "NINE_CLASSES",
    "PROGRAM_ANCHOR_PREFIX",
    "freeze_live_worktree",
    "run_adversarial_control",
    "run_quiescent_baseline_control",
    "run_rollback_rehearsal",
    "protocol",
]
