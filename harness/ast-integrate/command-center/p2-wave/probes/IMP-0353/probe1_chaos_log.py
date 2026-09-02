#!/usr/bin/env python3
"""Probe 1: chaos abort at 20 random mid-write points; every log parses.

Evidence requirement (2): event-log integrity after aborting at 20 random
points mid-write. Control: a naive JSONL torn mid-line does NOT parse.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.abort import (  # noqa: E402
    chaos_midwrite_trials,
    naive_jsonl_torn_parses,
    parse_log_bytes,
)

SEED = 353
N = 20


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0353-p1-") as td:
        root = Path(td)
        chaos = chaos_midwrite_trials(root / "chaos", n=N, seed=SEED)
        naive_parses = naive_jsonl_torn_parses(root / "naive.jsonl", 12)

        # Re-read each trial file from disk (not the in-memory parse).
        disk_ok = 0
        for i in range(N):
            log_path = root / "chaos" / f"trial-{i:02d}" / "events.clog"
            parsed = parse_log_bytes(log_path.read_bytes())
            if parsed["parseable"] and not parsed["torn"] and parsed["events"]:
                disk_ok += 1

        failed = [t for t in chaos["trials"] if not t["ok"]]
        out = {
            "probe": "probe1-chaos-midwrite",
            "unit_id": "IMP-0353",
            "n": N,
            "seed": SEED,
            "frame_len": chaos["frame_len"],
            "all_parse": chaos["all_parse"],
            "disk_ok": disk_ok,
            "naive_jsonl_torn_parses": naive_parses,
            "naive_control_fired": (not naive_parses),
            "failed_trials": failed[:5],
            "pass": (
                chaos["all_parse"]
                and disk_ok == N
                and not naive_parses
                and len(chaos["trials"]) == N
            ),
        }
        print(json.dumps(out, sort_keys=True))
        if not out["pass"]:
            print("FAILED:IMP-0353-probe1 chaos log integrity")
            return 1
        print("SUCCESS:IMP-0353-probe1 chaos abort at 20 points, log parses every time")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
