#!/usr/bin/env python3
"""Refuse-to-raise headroom guard (BLD-0057 reference implementation).

Production IMP-0445 is not on this worktree. This module is the scale-model
guard the unit verifies: it reads commit charge AND process/handle counts,
refuses to raise concurrency, and never kills a shared service.

A kill-based mutant is provided only as the named failure class
(FC-11328 / spec:11328) so probes can prove our real guard is not that class.
"""
from __future__ import annotations

import os
import signal
from dataclasses import dataclass, field
from typing import Any

ABORT_COMMIT_RATIO = 0.70


@dataclass
class Decision:
    allow: bool
    action: str
    reason: str
    signals: dict[str, Any] = field(default_factory=dict)


class HeadroomGuard:
    """Admit a new child only when both live signals are under abort watermarks."""

    def __init__(
        self,
        *,
        max_tagged: int,
        max_commit_delta_bytes: int,
        protected_pids: set[int] | None = None,
        abort_commit_ratio: float = ABORT_COMMIT_RATIO,
    ) -> None:
        self.max_tagged = max_tagged
        self.max_commit_delta_bytes = max_commit_delta_bytes
        self.protected_pids = set(protected_pids or ())
        self.abort_commit_ratio = abort_commit_ratio

    def admit(
        self,
        *,
        snapshot: dict[str, Any],
        tagged_count: int,
        commit_delta_bytes: int,
        candidate_pid: int | None = None,
    ) -> Decision:
        signals = {
            "commit_ratio": snapshot.get("commit_ratio"),
            "committed_as_bytes": snapshot.get("committed_as_bytes"),
            "commit_limit_bytes": snapshot.get("commit_limit_bytes"),
            "process_count": snapshot.get("process_count"),
            "fd_allocated": snapshot.get("fd_allocated"),
            "tagged_count": tagged_count,
            "commit_delta_bytes": commit_delta_bytes,
            "ram_used_ratio": snapshot.get("ram_used_ratio"),
        }
        if candidate_pid is not None and candidate_pid in self.protected_pids:
            return Decision(
                allow=True,
                action="SPARE",
                reason="protected-shared-service",
                signals=signals,
            )
        ratio = snapshot.get("commit_ratio")
        if ratio is not None and float(ratio) >= self.abort_commit_ratio:
            return Decision(
                allow=False,
                action="REFUSE_RAISE",
                reason="live-commit-ratio-abort",
                signals=signals,
            )
        if tagged_count >= self.max_tagged:
            return Decision(
                allow=False,
                action="REFUSE_RAISE",
                reason="tagged-process-ceiling",
                signals=signals,
            )
        if commit_delta_bytes >= self.max_commit_delta_bytes:
            return Decision(
                allow=False,
                action="REFUSE_RAISE",
                reason="sandbox-commit-delta",
                signals=signals,
            )
        return Decision(allow=True, action="ALLOW", reason="under-ceiling", signals=signals)


def kill_based_mutant(pids: list[int]) -> dict[str, Any]:
    """Named failure class: a memory guard that SIGKILLs whatever it sees."""
    killed: list[int] = []
    errors: list[str] = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            killed.append(pid)
        except OSError as exc:
            errors.append(f"{pid}:{exc}")
    return {
        "class": "kill-based memory guard terminates a live shared service",
        "spec": "11328",
        "killed": killed,
        "errors": errors,
    }
