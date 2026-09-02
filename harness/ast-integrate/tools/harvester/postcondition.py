"""Harvest postcondition: an empty harvest is FAILED even when the copy exits 0.

The copy step's exit code is never sufficient for SUCCESS. The gate compares a
before/after snapshot of the destination tree and demands a non-empty delta:
more files, more bytes, or changed content. A harvest that leaves the tree
byte-identical is a silent no-op and is classified FAILED with
``REASON_SILENT_NOOP`` regardless of the process exit code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REASON_SILENT_NOOP = "silent-noop-harvest"
REASON_OK = "ok-nonempty-delta"
REASON_PROCESS_FAILED = "copy-process-nonzero-exit"


@dataclass
class Snap:
    """Sorted (relative path, size) listing of a tree plus its totals."""

    file_count: int
    total_bytes: int
    digest: tuple[tuple[str, int], ...]

    def as_map(self) -> dict[str, int]:
        return dict(self.digest)

    def to_dict(self) -> dict[str, Any]:
        return {"file_count": self.file_count, "total_bytes": self.total_bytes}


@dataclass
class Delta:
    """What changed between two snapshots of the destination tree."""

    nonempty: bool
    file_delta: int
    byte_delta: int
    added_paths: tuple[str, ...] = ()
    removed_paths: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()

    @property
    def artifact_count_delta(self) -> int:
        return self.file_delta

    @property
    def bytes_delta(self) -> int:
        return self.byte_delta

    def to_dict(self) -> dict[str, Any]:
        return {
            "nonempty": self.nonempty,
            "artifact_count_delta": self.artifact_count_delta,
            "bytes_delta": self.bytes_delta,
            "added_paths": list(self.added_paths),
            "removed_paths": list(self.removed_paths),
            "changed_paths": list(self.changed_paths),
        }


@dataclass
class Verdict:
    """Classification of one harvest attempt."""

    state: str
    reason_id: str | None
    process_exit_code: int
    attempts: int
    before: Snap
    after: Snap
    delta: Delta
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason_id": self.reason_id,
            "process_exit_code": self.process_exit_code,
            "attempts": self.attempts,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "delta": self.delta.to_dict(),
            "notes": list(self.notes),
        }


def snapshot(root: Path) -> Snap:
    """Walk ``root`` and record every regular file with its size."""
    root = Path(root)
    files: list[tuple[str, int]] = []
    total = 0
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                size = p.stat().st_size
                files.append((p.relative_to(root).as_posix(), size))
                total += size
    return Snap(file_count=len(files), total_bytes=total, digest=tuple(files))


def independent_walk_counts(root: Path) -> tuple[int, int]:
    """Second, os.walk-based ``(file_count, total_bytes)`` to cross-check ``snapshot``."""
    n = 0
    total = 0
    root = Path(root)
    if root.exists():
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                p = Path(dirpath) / name
                if p.is_file() and not p.is_symlink():
                    n += 1
                    total += p.stat().st_size
    return n, total


def compute_delta(before: Snap, after: Snap) -> Delta:
    """Path-level diff of two snapshots; nonempty iff anything changed."""
    old = before.as_map()
    new = after.as_map()
    added = tuple(sorted(set(new) - set(old)))
    removed = tuple(sorted(set(old) - set(new)))
    changed = tuple(sorted(p for p in set(old) & set(new) if old[p] != new[p]))
    file_delta = after.file_count - before.file_count
    byte_delta = after.total_bytes - before.total_bytes
    nonempty = bool(added or removed or changed or file_delta or byte_delta)
    return Delta(
        nonempty=nonempty,
        file_delta=file_delta,
        byte_delta=byte_delta,
        added_paths=added,
        removed_paths=removed,
        changed_paths=changed,
    )


def classify(before: Snap, after: Snap, exit_code: int, attempts: int = 1) -> Verdict:
    """SUCCESS only on a non-zero exit AND a non-empty destination delta."""
    delta = compute_delta(before, after)
    code = int(exit_code)
    if code != 0:
        return Verdict(
            state="FAILED",
            reason_id=REASON_PROCESS_FAILED,
            process_exit_code=code,
            attempts=attempts,
            before=before,
            after=after,
            delta=delta,
            notes=[f"copy process exited {code}"],
        )
    if not delta.nonempty:
        return Verdict(
            state="FAILED",
            reason_id=REASON_SILENT_NOOP,
            process_exit_code=code,
            attempts=attempts,
            before=before,
            after=after,
            delta=delta,
            notes=["exit 0 but destination tree is byte-identical: silent no-op"],
        )
    return Verdict(
        state="SUCCESS",
        reason_id=REASON_OK,
        process_exit_code=code,
        attempts=attempts,
        before=before,
        after=after,
        delta=delta,
    )
