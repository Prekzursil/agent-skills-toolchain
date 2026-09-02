#!/usr/bin/env python3
"""Named probe 1: live 21-condition evaluation plus detector controls.

Re-derives every live verdict from disk (and in-memory fixtures). Does not
read a prior-lane sidecar. Detector controls must fire on known-broken and
stay silent on known-good for all 21 predicates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import evaluate as E  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0187.json"


def main() -> int:
    ctrls = E.assert_controls()
    live_rows = E.evaluate_world(E.build_live_world(REPO))
    if len(live_rows) != 21:
        print(f"FAILED:CNF-0187-probe1 row_count={len(live_rows)}")
        return 1
    if any(r["verdict"] not in {"TRUE", "FALSE", "NOT-CHECKED"} for r in live_rows):
        print("FAILED:CNF-0187-probe1 illegal verdict")
        return 1
    if any(not r["detector_control"]["fired_on_broken"] for r in live_rows):
        print("FAILED:CNF-0187-probe1 detector silent on broken")
        return 1
    if any(not r["detector_control"]["silent_on_good"] for r in live_rows):
        print("FAILED:CNF-0187-probe1 detector fired on good")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0187-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0187":
        print("FAILED:CNF-0187-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:CNF-0187" not in text:
        print("FAILED:CNF-0187-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0187-probe1 self-declared", doc.get("state"))
        return 1
    payload = E.gate_payload(doc)
    art_rows = payload.get("conditions") or []
    if len(art_rows) != 21:
        print(f"FAILED:CNF-0187-probe1 artifact rows={len(art_rows)}")
        return 1
    mismatch = []
    for live, art in zip(live_rows, art_rows):
        if int(art.get("id") or 0) != live["id"]:
            mismatch.append(("id", live["id"], art.get("id")))
            continue
        if art.get("verdict") != live["verdict"]:
            mismatch.append(("verdict", live["id"], live["verdict"], art.get("verdict")))
    if mismatch:
        print("FAILED:CNF-0187-probe1 live/artifact mismatch", mismatch[:8])
        return 1
    if payload.get("overall_verdict") != E.overall_verdict(live_rows):
        print("FAILED:CNF-0187-probe1 overall mismatch", payload.get("overall_verdict"))
        return 1
    if payload.get("overall_verdict") == "GO" and any(
        r["verdict"] != "TRUE" for r in live_rows
    ):
        print("FAILED:CNF-0187-probe1 NOT-CHECKED folded into GO")
        return 1
    c13 = next(r for r in live_rows if r["id"] == 13)
    if c13["verdict"] == "TRUE":
        print("FAILED:CNF-0187-probe1 condition 13 TRUE under this tree")
        return 1
    counts = {"TRUE": 0, "FALSE": 0, "NOT-CHECKED": 0}
    for r in live_rows:
        counts[r["verdict"]] += 1
    summary = {
        "counts": counts,
        "overall": E.overall_verdict(live_rows),
        "controls_pass": all(c["pass"] for c in ctrls),
        "c13": {"verdict": c13["verdict"], "reason": c13["reason"]},
        "c20": next(r for r in live_rows if r["id"] == 20),
    }
    print(json.dumps(summary, default=str))
    print(
        f"counts TRUE={counts['TRUE']} FALSE={counts['FALSE']} "
        f"NOT-CHECKED={counts['NOT-CHECKED']} overall={summary['overall']}"
    )
    print("SUCCESS:CNF-0187-probe1 live-eval detector-controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
