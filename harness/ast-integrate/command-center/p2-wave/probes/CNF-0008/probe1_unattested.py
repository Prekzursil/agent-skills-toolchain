#!/usr/bin/env python3
"""Probe 1: planted receipt claiming a probe that was never run must be unattested."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from attestation import artifact_controls, opposite_controls  # noqa: E402
from controls import run_both  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0008-execution-attestation.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0008-p1-") as tmp:
        result = run_both(Path(tmp))
    planted = result["planted"]
    genuine = result["genuine"]
    if not result["ok"] or not opposite_controls(planted, genuine):
        print("FAILED:CNF-0008-probe1 controls not classified oppositely")
        print(json.dumps({"planted": planted, "genuine": genuine}, indent=2, default=str)[:4000])
        return 1
    if planted.get("unattested") is not True:
        print("FAILED:CNF-0008-probe1 planted receipt was not flagged unattested")
        return 1
    if planted.get("original_verdict") != "CONFIRMED":
        print("FAILED:CNF-0008-probe1 planted original verdict was not CONFIRMED")
        return 1
    if planted.get("attested_verdict") != "NOT-CHECKED":
        print(
            "FAILED:CNF-0008-probe1 planted was not downgraded to NOT-CHECKED: "
            f"{planted.get('attested_verdict')}"
        )
        return 1
    if planted.get("ledger_row_id") or planted.get("produced_path"):
        print("FAILED:CNF-0008-probe1 planted unexpectedly attested")
        return 1
    if planted.get("id") != "receipt-planted-unattested":
        print(f"FAILED:CNF-0008-probe1 planted id {planted.get('id')}")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0008-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0008-probe1 self-declared {doc.get('state')}")
        return 1
    controls = artifact_controls(doc)
    ctrl = controls.get("planted") or {}
    if ctrl.get("unattested") is not True:
        print("FAILED:CNF-0008-probe1 artifact planted control not unattested")
        return 1
    if not controls.get("classified_oppositely"):
        print("FAILED:CNF-0008-probe1 artifact classified_oppositely false")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0008 emitted only when" not in text:
        print("FAILED:CNF-0008-probe1 catalog sentinel absent from artifact")
        return 1

    out = {
        "probe": "probe1-unattested",
        "unit_id": "CNF-0008",
        "planted_unattested": True,
        "planted_downgraded_to": planted["attested_verdict"],
        "classified_oppositely": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "planted id={id} unattested={u} original={o} attested={a} reason={r}".format(
            id=planted["id"],
            u=planted["unattested"],
            o=planted["original_verdict"],
            a=planted["attested_verdict"],
            r=planted["reason"],
        )
    )
    print("SUCCESS:CNF-0008-probe1 planted unattested receipt flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
