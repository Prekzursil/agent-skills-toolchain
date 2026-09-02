#!/usr/bin/env python3
"""Named probe 2: corrupted checkpoint refused + silent-redo detector.

Independent of probe 1's artifact-hash comparison. Re-runs the two controls
live and checks the confirmation file recorded the same outcomes.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0079-resume-parity.json"


def control_by_id(doc: dict, cid: str) -> dict | None:
    for row in doc.get("controls") or []:
        if row.get("id") == cid:
            return row
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0079-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0079":
        print("FAILED:CNF-0079-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:CNF-0079" not in json.dumps(doc):
        print("FAILED:CNF-0079-probe2 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0079-p2-") as tmp:
        root = Path(tmp)
        corrupt = E.corrupt_checkpoint_refused(root / "corrupt")
        detector = E.redo_completed_detected(root / "redo")

    if not corrupt.get("refused"):
        print("FAILED:CNF-0079-probe2 corrupt checkpoint was not refused")
        print(json.dumps(corrupt, indent=2)[:2000])
        return 1
    if not corrupt.get("effects_unchanged") or not corrupt.get("stages_unchanged"):
        print("FAILED:CNF-0079-probe2 corrupt resume executed work")
        print(json.dumps(corrupt, indent=2)[:2000])
        return 1
    if not detector.get("fired"):
        print("FAILED:CNF-0079-probe2 silent-redo detector did not fire")
        print(json.dumps(detector, indent=2)[:2000])
        return 1

    rec_corrupt = control_by_id(doc, "corrupt-checkpoint-refuse")
    rec_redo = control_by_id(doc, "silent-redo-detector")
    if not rec_corrupt or rec_corrupt.get("fired") is not True or rec_corrupt.get("result") != "PASS":
        print("FAILED:CNF-0079-probe2 artifact corrupt control drift", rec_corrupt)
        return 1
    if not rec_redo or rec_redo.get("fired") is not True or rec_redo.get("result") != "PASS":
        print("FAILED:CNF-0079-probe2 artifact redo-detector drift", rec_redo)
        return 1

    out = {
        "probe": "probe2-corrupt-checkpoint",
        "unit_id": "CNF-0079",
        "corrupt_refused": True,
        "corrupt_exit_code": corrupt["exit_code"],
        "no_partial_run": True,
        "silent_redo_detected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"corrupt_refused={corrupt['refused']} exit={corrupt['exit_code']} "
        f"redo_fired={detector['fired']} effects={detector['effects']}"
    )
    print("SUCCESS:CNF-0079-probe2 corrupt-checkpoint refusal and redo detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
