#!/usr/bin/env python3
"""Probe 2: adversarial refuter constructs a false positive and a false negative.

Does not re-read the conclusion. Re-runs the gate on planted candidates:
  * false positive: a genuine analysis whose subject is background dispatch
    (naive substring gate REJECTS; role-aware gate must ACCEPT)
  * false negative: a receipt wrapped with a plausible digest/path/sentinel
    (must still be FAILED and unable to satisfy the barrier)

A gate that rejects the mention candidate is a use-vs-mention defect.
A gate that accepts the digest-wrapped receipt lets a receipt satisfy a barrier.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402


def main() -> int:
    report = S.run_corpus()
    fp = report["refute_false_positive"]
    fn = report["refute_false_negative"]
    checks = [
        ("fp accepted by role-aware gate", report["fp_accepted"]),
        ("fp role RESULT", fp["got_role"] == S.ROLE_RESULT),
        ("fp naive foil FAILED", fp["naive_decision"] == S.DECISION_FAILED),
        ("fn rejected by role-aware gate", report["fn_rejected"]),
        ("fn role RECEIPT", fn["got_role"] == S.ROLE_RECEIPT),
        ("fn cannot satisfy barrier", fn["can_satisfy_barrier"] is False),
        ("fn admitted False", fn["admitted"] is False),
        ("fn opener is receipt speech", fn["opener_is_receipt_speech"] is True),
        ("receipt cannot satisfy barrier", report["receipt_cannot_satisfy_barrier"]),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:IMP-0425-probe2 {name}")
            print(json.dumps({"fp": fp, "fn": fn}, indent=2, default=str)[:3000])
            return 1
    art_ok, why = S.artifact_ok()
    if not art_ok:
        print(f"FAILED:IMP-0425-probe2 artifact {why}")
        return 1
    doc = json.loads(S.ART.read_text(encoding="utf-8"))
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:IMP-0425-probe2 reviewer verdict not PASS")
        return 1
    print("SUCCESS:IMP-0425-probe2 refuter false-positive mention accepted, false-negative receipt rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
