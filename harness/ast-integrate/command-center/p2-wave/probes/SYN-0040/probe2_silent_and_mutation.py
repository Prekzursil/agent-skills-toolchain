#!/usr/bin/env python3
"""Probe 2: SILENT-IN-BOTH fails the matrix; mutation sweep turns gates red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from constants import CALIBRATION_ID, OUTPUT_REL, REPO, UNIT_ID  # noqa: E402
from matrix import classify, matrix_fail_reasons, run_bucket  # noqa: E402
from schema_util import report_body  # noqa: E402

ART = REPO / OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0040-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    live = run_bucket()
    cal = live["calibration"]
    if cal["id"] != CALIBRATION_ID:
        return fail(f"calibration id {cal['id']}")
    if cal["broken_exit_code"] != 0 or cal["good_exit_code"] != 0:
        return fail("inert detector did not exit 0 in both states")
    if cal["verdict"] != "SILENT-IN-BOTH":
        return fail(f"inert verdict {cal['verdict']}")
    if classify(0, 0) != "SILENT-IN-BOTH":
        return fail("classify(0,0) drifted")
    reasons = matrix_fail_reasons(live["gates"] + [cal])
    if not any(item["reason"] == "silent-in-both" for item in reasons):
        return fail("SILENT-IN-BOTH did not fail the matrix")
    if not live["silent_calibration_fails_matrix"]:
        return fail("silent_calibration_fails_matrix false")

    body = report_body(doc)
    art_cal = (body.get("calibration") or {}).get("row") or {}
    if art_cal.get("verdict") != "SILENT-IN-BOTH":
        return fail("artifact calibration not SILENT-IN-BOTH")
    if not (body.get("calibration") or {}).get("fails_the_matrix"):
        return fail("artifact did not record that silent-in-both fails the matrix")

    mutations = live["mutations"]
    if not mutations or not all(m.get("fired") for m in mutations):
        print(json.dumps(mutations, indent=2)[:4000])
        return fail("mutation sweep did not fire every owning gate")
    art_mut = (body.get("mutation_sweep") or {}).get("rows") or []
    live_mut_fp = [(m["id"], m["mutation"], m["fired"]) for m in mutations]
    art_mut_fp = [(m["id"], m["mutation"], m["fired"]) for m in art_mut]
    if live_mut_fp != art_mut_fp:
        return fail("mutation sweep fingerprint mismatch")

    print(
        json.dumps(
            {
                "probe": "probe2-silent-and-mutation",
                "unit_id": UNIT_ID,
                "pass": True,
                "silent_in_both": True,
                "fails_matrix": True,
                "mutations_fired": len(mutations),
                "reviewer_starts_from_the_control": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"silent_in_both=True fails_matrix=True "
        f"mutations_fired={len(mutations)}/{len(mutations)}"
    )
    print("SUCCESS:SYN-0040-probe2 silent-in-both-fails-matrix mutation-sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
