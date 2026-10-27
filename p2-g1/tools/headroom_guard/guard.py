"""Commit-charge headroom guard — RAM percent is a control, not the predicate."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any

from headroom_guard.commit_charge import MemorySnapshot

RAM_ONLY_CONTROL_PERCENT = 80.0
FIRE_RATIO = 0.85
RESCUE_RESERVE = 512 * 1024 * 1024
PROTECTED = frozenset({"sshd", "systemd", "init", "explorer.exe"})


@dataclass
class Decision:
    fired: bool
    allow_raise: bool
    action: str
    kill_shared_service: bool
    counter_read: str
    reasons: list[str] = field(default_factory=list)
    readout: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fired": self.fired,
            "allow_raise": self.allow_raise,
            "action": self.action,
            "kill_shared_service": self.kill_shared_service,
            "counter_read": self.counter_read,
            "reasons": list(self.reasons),
            "readout": dict(self.readout),
        }


@dataclass
class ShedRequest:
    mode: str
    target_name: str
    target_pid: int | None = None


@dataclass
class ShedResult:
    refused: bool
    killed_pids: list[int]
    action: str
    protected_hit: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "refused": self.refused,
            "killed_pids": list(self.killed_pids),
            "action": self.action,
            "protected_hit": self.protected_hit,
        }


def ram_percent_would_fire(snapshot: MemorySnapshot) -> bool:
    return snapshot.ram_percent >= RAM_ONLY_CONTROL_PERCENT


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class HeadroomGuard:
    COUNTER = "Committed_AS/CommitLimit (committed_bytes/commit_limit_bytes)"

    def decide(
        self,
        current_concurrency: int,
        requested_concurrency: int,
        snapshot: MemorySnapshot,
    ) -> Decision:
        committed_bytes = snapshot.committed_bytes
        commit_limit_bytes = snapshot.commit_limit_bytes
        commit_headroom_bytes = snapshot.commit_headroom_bytes
        ratio = committed_bytes / commit_limit_bytes if commit_limit_bytes else 0.0
        reasons: list[str] = []
        fired = False
        if ratio >= FIRE_RATIO:
            fired = True
            reasons.append("commit-ratio-threshold")
        if commit_headroom_bytes < RESCUE_RESERVE:
            fired = True
            reasons.append("rescue-shell-headroom")
        raising = requested_concurrency > current_concurrency
        if fired and raising:
            action = "REFUSE_RAISE_CONCURRENCY"
            allow = False
        elif fired:
            action = "HOLD_OR_LOWER_ALLOWED"
            allow = True
        else:
            action = "ALLOW"
            allow = True
        return Decision(
            fired=fired,
            allow_raise=allow,
            action=action,
            kill_shared_service=False,
            counter_read=self.COUNTER,
            reasons=reasons,
            readout={
                "committed_bytes": committed_bytes,
                "commit_limit_bytes": commit_limit_bytes,
                "commit_headroom_bytes": commit_headroom_bytes,
            },
        )

    def shed(self, request: ShedRequest) -> ShedResult:
        protected = request.target_name in PROTECTED
        return ShedResult(
            refused=True,
            killed_pids=[],
            action="REFUSE_RAISE_CONCURRENCY",
            protected_hit=protected,
        )
