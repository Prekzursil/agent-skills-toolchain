"""Copy remote tree; exit 0 even when empty (postcondition must fail it)."""
from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Transfer:
    exit_code: int = 0
    copied: int = 0


def transfer_tree(remote: Path, dest: Path) -> Transfer:
    remote = Path(remote)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    if remote.exists():
        for p in remote.rglob("*"):
            if p.is_file():
                rel = p.relative_to(remote)
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, target)
                copied += 1
    return Transfer(exit_code=0, copied=copied)


def run_harvest(
    remote: Path,
    dest: Path,
    max_attempts: int = 2,
    backoff_seconds: tuple[float, ...] = (0.0,),
    between_attempts=None,
    **kwargs,
):
    from postcondition import REASON_SILENT_NOOP, classify, snapshot

    last = None
    for attempt in range(1, int(max_attempts) + 1):
        before = snapshot(dest)
        tr = transfer_tree(remote, dest)
        after = snapshot(dest)
        last = classify(before, after, tr.exit_code, attempts=attempt)
        if last.state != "FAILED":
            return last
    return last


def main(argv: list[str] | None = None) -> int:
    from postcondition import classify, snapshot

    p = argparse.ArgumentParser()
    p.add_argument("--remote", required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--max-attempts", type=int, default=2)
    p.add_argument("--backoff-seconds", type=float, default=0)
    args = p.parse_args(argv)
    remote = Path(args.remote)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(1, args.max_attempts + 1):
        before = snapshot(dest)
        tr = transfer_tree(remote, dest)
        after = snapshot(dest)
        last = classify(before, after, tr.exit_code, attempts=attempt)
        if last.state != "FAILED":
            print("SUCCESS:harvest")
            return 0
    print("FAILED:silent-noop-harvest")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
