"""Empty harvest is FAILED even when the copy step exits 0 (IMP-0431)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REASON_SILENT_NOOP = "silent-noop-harvest"
REASON_OK = "ok-nonempty-delta"


@dataclass
class Snap:
    file_count: int
    total_bytes: int
    digest: tuple[tuple[str, int], ...]


@dataclass
class Delta:
    nonempty: bool
    file_delta: int
    byte_delta: int


@dataclass
class Verdict:
    state: str
    reason_id: str | None
    process_exit_code: int
    attempts: int
    before: Snap
    after: Snap
    delta: Delta


def independent_walk_counts(root: Path) -> dict[str, int]:
    snap = snapshot(root)
    return {"file_count": snap.file_count, "total_bytes": snap.total_bytes}


def snapshot(root: Path) -> Snap:
    root = Path(root)
    files = []
    total = 0
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file():
                sz = p.stat().st_size
                files.append((p.relative_to(root).as_posix(), sz))
                total += sz
    return Snap(file_count=len(files), total_bytes=total, digest=tuple(files))


def classify(before: Snap, after: Snap, exit_code: int, attempts: int = 1) -> Verdict:
    file_delta = after.file_count - before.file_count
    byte_delta = after.total_bytes - before.total_bytes
    nonempty = file_delta > 0 or byte_delta > 0
    if nonempty:
        return Verdict(
            state="SUCCESS",
            reason_id=None,
            process_exit_code=int(exit_code),
            attempts=attempts,
            before=before,
            after=after,
            delta=Delta(nonempty=True, file_delta=file_delta, byte_delta=byte_delta),
        )
    return Verdict(
        state="FAILED",
        reason_id=REASON_SILENT_NOOP,
        process_exit_code=int(exit_code),
        attempts=attempts,
        before=before,
        after=after,
        delta=Delta(nonempty=False, file_delta=file_delta, byte_delta=byte_delta),
    )
