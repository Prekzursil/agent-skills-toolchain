#!/usr/bin/env python3
"""CLI for Phase-0 baseline capture (TST-0302)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from baseline import BaselineStore, DirtyTreeRejected, capture_baseline  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--repo", required=True)
    cap.add_argument("--store", required=True)
    cap.add_argument("--id", required=True)
    cap.add_argument("--accept-dirty", action="store_true")
    args = p.parse_args(argv)
    store = BaselineStore(args.store)
    try:
        rec = capture_baseline(Path(args.repo), store, args.id, accept_dirty=args.accept_dirty)
    except DirtyTreeRejected as exc:
        print(f"DirtyTreeRejected: {exc}", file=sys.stderr)
        return 2
    print(rec["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
