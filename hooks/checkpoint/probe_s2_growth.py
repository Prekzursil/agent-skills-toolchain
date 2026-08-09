#!/usr/bin/env python3
"""Settling experiment for WATCHDOG-DESIGN.md section 8, UNVERIFIED #1.

Question: does a Task-subagent's `agent-<id>.jsonl` grow MONOTONICALLY while the subagent runs,
or does the host buffer and flush only at completion? If it is the latter, signal S2
(byte-growth) is worthless for in-process subagents and the watchdog design collapses to S1+S4.

Method: two size samples separated by --wait seconds over every `agent-*.jsonl` in the newest
`subagents/` dir. Read-only. Byte-GROWTH, never mtime -- a file that merely exists and is
readable proves nothing (monitorcore: "a readable file is not a live feed").

    python probe_s2_growth.py --wait 20

Terminal state: SUCCESS: (growth observed on >=1 file => S2 is usable) /
FAILED: (no growth anywhere => either nothing was running, or S2 does not work -- the two are
NOT distinguishable by this probe alone, which is exactly why it prints the sample counts).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"


def sample(d: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in d.glob("agent-*.jsonl"):
        try:
            out[f.name] = f.stat().st_size
        except OSError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=float, default=20.0)
    ap.add_argument("--dir", default="")
    args = ap.parse_args()

    if args.dir:
        target = Path(args.dir)
    else:
        cands = sorted(
            ROOT.glob("*/*/subagents"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if not cands:
            print("FAILED:s2-probe NOT-CHECKED no subagents/ directory found")
            return 1
        target = cands[0]

    a = sample(target)
    if not a:
        print(f"FAILED:s2-probe NOT-CHECKED no agent-*.jsonl in {target}")
        return 1
    time.sleep(args.wait)
    b = sample(target)

    grew = {k: b[k] - a[k] for k in a if k in b and b[k] > a[k]}
    print(f"dir={target}")
    print(f"files_sampled={len(a)} wait={args.wait}s files_that_GREW={len(grew)}")
    for name, delta in sorted(grew.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  +{delta:>9} B  {name}")
    if grew:
        print(
            f"\nSUCCESS:s2-probe growth observed on {len(grew)}/{len(a)} files -> S2 is a usable liveness signal"
        )
        return 0
    print(
        "\nFAILED:s2-probe NO growth on any of "
        f"{len(a)} files in {args.wait}s. This is AMBIGUOUS by construction: either nothing was "
        "running, or the host buffers until completion. Re-run while a subagent is known live."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
