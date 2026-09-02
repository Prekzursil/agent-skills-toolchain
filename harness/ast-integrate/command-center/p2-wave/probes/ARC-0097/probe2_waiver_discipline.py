#!/usr/bin/env python3
"""Probe 2: waiver discipline both-states control.

Unsatisfiable conditions may only close by owner-recorded waiver or
owner-recorded equivalent formulation, never by reinterpretation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stopping as S  # noqa: E402
import waiver as W  # noqa: E402

OUT = HERE / "probe2-waiver-discipline.raw.json"


def check_contract(doc: dict) -> list[str]:
    errs: list[str] = []
    payload = S.contract_payload(doc)
    handling = payload.get("sc13_handling") or {}
    if handling.get("as_written") != "UNSATISFIABLE-AS-WRITTEN":
        errs.append("as-written-laundered")
    if handling.get("reinterpretation_forbidden") is not True:
        errs.append("reinterpretation-not-forbidden")
    method = handling.get("close_method")
    if method not in W.ALLOWED_CLOSE:
        errs.append(f"close-method={method}")
    if method == "REINTERPRETATION":
        errs.append("closed-by-reinterpretation")
    disc = payload.get("waiver_discipline") or {}
    forbidden = set(disc.get("forbidden_close_methods") or [])
    if "REINTERPRETATION" not in forbidden:
        errs.append("discipline-omits-reinterpretation")
    allowed = set(disc.get("allowed_close_methods") or [])
    if not allowed.issubset(W.ALLOWED_CLOSE):
        errs.append("discipline-allows-unknown")
    # Must not claim SC-13 SATISFIABLE as written.
    for row in payload.get("stopping_conditions") or []:
        if row.get("id") == 13 and row.get("satisfiability_under_pr_only") != (
            "UNSATISFIABLE-AS-WRITTEN"
        ):
            errs.append("sc13-row-laundered")
    return errs


def main() -> int:
    ctx = S.load_owner_context()
    ctl = W.run_controls(ctx["oq9"])
    errs: list[str] = []
    if not ctl["ok"]:
        errs.append("controls-failed")
    if not ctl["fired_on_bad"]:
        errs.append("did-not-fire-on-bad")
    if not ctl["silent_on_good"]:
        errs.append("did-not-accept-good")
    doc = S.load_contract()
    contract_checked = False
    if doc is not None:
        contract_checked = True
        errs.extend(check_contract(doc))
    payload = {
        "probe": "probe2-waiver-discipline",
        "unit_id": "ARC-0097",
        "fired_on_bad": ctl["fired_on_bad"],
        "silent_on_good": ctl["silent_on_good"],
        "cases": {
            k: {"accepted": v["accepted"], "reason": v["reason"], "method": v["method"]}
            for k, v in ctl["cases"].items()
        },
        "contract_present": contract_checked,
        "errors": errs,
        "pass": not errs,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired_on_bad={ctl['fired_on_bad']} silent_on_good={ctl['silent_on_good']}"
        f" contract_checked={contract_checked}"
    )
    for name, case in ctl["cases"].items():
        print(f"  {name} accepted={case['accepted']} method={case['method']}")
    if errs:
        print("FAILED:ARC-0097-probe2 " + "; ".join(errs[:8]))
        return 1
    print("SUCCESS:ARC-0097-probe2 waiver discipline rejects reinterpretation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
