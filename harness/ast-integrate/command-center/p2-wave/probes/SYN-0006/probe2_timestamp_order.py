#!/usr/bin/env python3
"""Probe 2: timestamp order, closed-without-anchor, reopen owner-question."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detect as D  # noqa: E402

ART = REPO / D.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0006-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if D.SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")

    for row in doc.get("entries") or []:
        verdict = row.get("verdict")
        dts = str(row.get("decision_timestamp") or "")
        ets = str(row.get("evidence_timestamp") or "")
        if verdict in {"SUPERSEDED-UNRECORDED", "REOPEN-REQUIRED"}:
            if not row.get("decision_anchor"):
                return fail(f"{row.get('id')} closed without decision_anchor")
            if not row.get("contradicting_evidence_anchor"):
                return fail(f"{row.get('id')} closed without contradicting_evidence_anchor")
            if ets <= dts:
                return fail(f"{row.get('id')} evidence_timestamp not after decision")
        if verdict == "REOPEN-REQUIRED" and len(str(row.get("owner_question") or "")) < 20:
            return fail(f"{row.get('id')} missing owner_question")

    scratch = Path(tempfile.mkdtemp(prefix="syn0006-p2-"))
    controls = D.run_timestamp_controls(scratch)
    print(json.dumps({k: {"ok": v.get("ok")} for k, v in controls.items()}, sort_keys=True))
    bad = [k for k, v in controls.items() if not v.get("ok")]
    if bad:
        print(json.dumps(controls, default=str)[:4000])
        return fail(f"controls failed: {bad}")

    required = (
        "earlier-evidence-cannot-contradict",
        "later-evidence-reverses",
        "currently-true-not-superseded",
        "known-present-absent-when-line-missing",
        "closed-without-anchor-rejected",
        "reopen-without-question-rejected",
        "reopen-with-question-accepted",
    )
    missing = [k for k in required if k not in controls]
    if missing:
        return fail(f"missing controls {missing}")

    print(
        "earlier_rejected=True later_reverses=True still_true_silent=True "
        "closed_without_anchor_rejected=True reopen_question_both_states=True"
    )
    print("SUCCESS:SYN-0006-probe2 timestamp-order both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
