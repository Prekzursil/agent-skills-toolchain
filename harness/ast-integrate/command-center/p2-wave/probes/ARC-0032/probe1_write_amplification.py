#!/usr/bin/env python3
"""Named probe 1: ledger write-amplification on a real batch.

Signal 1 is Path.stat().st_size. Signal 2 is `wc -c` (different process).
Disagreement is BLOCKED, not a picked winner. Requires >= 10 real dispatches.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

ART = REPO / "command-center/phase3/A5/COST.json"
N = 16
C = 4
BAND = 0.10


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0032-probe1 COST.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0032":
        print("FAILED:ARC-0032-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:ARC-0032" not in json.dumps(doc):
        print("FAILED:ARC-0032-probe1 sentinel absent")
        return 1
    recorded = float(doc["headline_numbers"]["ledger_bytes_per_unit"])

    with TemporaryDirectory(prefix="arc0032-p1-") as tmp:
        summary = R.run_batch(N, C, Path(tmp) / "batch")

    py_b = summary["ledger_bytes_python"]
    wc_b = summary["ledger_bytes_wc"]
    if int(py_b) != int(wc_b):
        print("FAILED:ARC-0032-probe1 write-amp signals disagree (BLOCKED, not picked)")
        print(json.dumps({"python_stat_st_size": py_b, "wc_c": wc_b}))
        return 1
    if summary["dispatch_count"] < 10:
        print(f"FAILED:ARC-0032-probe1 dispatch_count={summary['dispatch_count']} want>=10")
        return 1
    per = py_b / N
    err = abs(per - recorded) / recorded if recorded else 1.0
    if err > BAND:
        print(
            f"FAILED:ARC-0032-probe1 bytes/unit live={per:.3f} recorded={recorded:.3f} "
            f"err={err:.3f} band={BAND}"
        )
        return 1
    out = {
        "probe": "probe1-write-amplification",
        "unit_id": "ARC-0032",
        "n": N,
        "concurrency": C,
        "dispatch_count": summary["dispatch_count"],
        "ledger_bytes_python": py_b,
        "ledger_bytes_wc": wc_b,
        "bytes_per_unit": round(per, 3),
        "recorded_bytes_per_unit": recorded,
        "error_frac": round(err, 6),
        "signals_agree": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"write_amp bytes/unit live={per:.3f} recorded={recorded:.3f} "
        f"dispatches={summary['dispatch_count']} py=wc={py_b}"
    )
    print("SUCCESS:ARC-0032-probe1 write-amplification real batch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
