#!/usr/bin/env python3
"""Named probe 1: sequential completion-path profile at 1x/10x/100x.

Attributes wall time to predicate evaluation, JSON serialisation, O_APPEND
write, fsync (absent on the production path), and lock wait (no userspace lock).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hotpath as hp  # noqa: E402


def main() -> int:
    loads = []
    for name, n in hp.LOADS:
        row = hp.profile_sequential(n, label=name)
        loads.append(row)
        if not row["integrity"]["all_present"]:
            print(json.dumps({"pass": False, "probe": "probe1-hotpath-profile", "loads": loads}, sort_keys=True))
            print(f"FAILED:ADV-0116-probe1 integrity lost at {name}")
            return 1
    fsync_arm = hp.fsync_comparison_arm(40)
    ten = next(r for r in loads if r["name"] == "10x")
    out = {
        "pass": True,
        "probe": "probe1-hotpath-profile",
        "unit_id": hp.UNIT,
        "load_definition": (
            "1x = 8 sequential unit-completion cycles (predicate.evaluate + "
            "event-log append). 10x=80, 100x=800. Process count stays 1 so the "
            "host bound in tests_required is honoured; 100x is event-count scale."
        ),
        "loads": loads,
        "at_10x": {
            "predicate_frac": ten["predicate_frac"],
            "append_frac": ten["append_frac"],
            "serialize_frac": ten["serialize_frac"],
            "fsync_frac": 0.0,
            "lock_wait_frac": 0.0,
            "wall_s": ten["wall_s"],
            "bytes_written": ten["bytes_written"],
        },
        "fsync_comparison_arm": fsync_arm,
        "production_path": {
            "fsync_in_append": False,
            "fcntl_used": False,
            "mechanism": "O_APPEND single os.write of one JSONL record",
        },
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"10x predicate_frac={ten['predicate_frac']} append_frac={ten['append_frac']} "
        f"lock_wait=0 fsync=0 wall={ten['wall_s']}s"
    )
    print("SUCCESS:ADV-0116-probe1 sequential hot-path profile 1x/10x/100x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
