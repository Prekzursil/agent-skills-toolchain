"""Harvest a remote tree into a destination, gated on a non-empty delta.

The copy step deliberately exits 0 even when the remote is empty: that is the
failure mode the postcondition exists for. ``run_harvest`` snapshots the
destination before and after each attempt and lets ``postcondition.classify``
decide; a byte-identical destination is a FAILED silent no-op no matter what
the copy reported, and only then is a retry attempted.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from postcondition import Verdict, classify, snapshot  # noqa: E402

BetweenAttempts = Callable[[int, Verdict, "Transfer"], None]


@dataclass
class Transfer:
    """Result of one copy pass: exit code and files copied."""

    exit_code: int = 0
    copied: int = 0
    copied_paths: list[str] = field(default_factory=list)


def transfer_tree(remote: Path, dest: Path) -> Transfer:
    """Copy every regular file under ``remote`` into ``dest``; exit 0 always."""
    remote = Path(remote)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    tr = Transfer()
    if remote.exists():
        for p in sorted(remote.rglob("*")):
            if p.is_file():
                rel = p.relative_to(remote)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
                tr.copied += 1
                tr.copied_paths.append(rel.as_posix())
    return tr


def run_harvest(
    remote: Path,
    dest: Path,
    max_attempts: int = 2,
    backoff_seconds: Sequence[float] = (0.0,),
    between_attempts: BetweenAttempts | None = None,
) -> Verdict:
    """Attempt the harvest up to ``max_attempts`` times.

    After each FAILED attempt that leaves retries, sleep the matching backoff
    (last value repeats) and invoke ``between_attempts(attempt, verdict,
    transfer)`` so callers can repair the remote before the next try. The
    returned verdict's ``attempts`` is the number of attempts actually made.
    """
    attempts = max(1, int(max_attempts))
    backoff = tuple(float(b) for b in backoff_seconds) or (0.0,)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    last: Verdict | None = None
    for attempt in range(1, attempts + 1):
        before = snapshot(dest)
        tr = transfer_tree(remote, dest)
        after = snapshot(dest)
        last = classify(before, after, tr.exit_code, attempts=attempt)
        if last.state == "SUCCESS":
            return last
        if attempt < attempts:
            delay = backoff[min(attempt - 1, len(backoff) - 1)]
            if delay > 0:
                time.sleep(delay)
            if between_attempts is not None:
                between_attempts(attempt, last, tr)
    assert last is not None
    return last


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--remote", required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--max-attempts", type=int, default=2)
    p.add_argument("--backoff-seconds", type=float, default=0.0)
    args = p.parse_args(argv)
    verdict = run_harvest(
        Path(args.remote),
        Path(args.dest),
        max_attempts=args.max_attempts,
        backoff_seconds=(args.backoff_seconds,),
    )
    if verdict.state == "SUCCESS":
        print(
            f"attempts={verdict.attempts} files+={verdict.delta.artifact_count_delta} "
            f"bytes+={verdict.delta.bytes_delta}"
        )
        print("SUCCESS:harvest")
        return 0
    print(f"attempts={verdict.attempts} reason={verdict.reason_id}")
    print(f"FAILED:{verdict.reason_id}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
