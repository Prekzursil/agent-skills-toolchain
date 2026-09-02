#!/usr/bin/env python3
"""Probe 1: planted unanchored claim REJECTED; fully anchored rationale PASSES.

Both states are required. A lint that always fails, or always passes, is
measuring nothing.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.workflow_forge.rationale import (  # noqa: E402
    REJECTED,
    PASS,
    emit_rationale,
    lint_rationale,
)

REQ = HERE / "fixtures" / "fully_anchored_request.json"
PLANTED = HERE / "fixtures" / "planted_unanchored.json"


def _load(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit(f"FAILED:IMP-0214-probe1 {path.name} is not an object")
    return doc


def main() -> int:
    req = _load(REQ)
    planted = _load(PLANTED)

    planted_lint = lint_rationale(planted, root=REPO)
    print(
        "planted",
        planted_lint["verdict"],
        "codes=",
        sorted({v["code"] for v in planted_lint["violations"]}),
    )
    if planted_lint["ok"] or planted_lint["verdict"] != REJECTED:
        print("FAILED:IMP-0214-probe1 planted unanchored claim was accepted")
        return 1
    codes = {v["code"] for v in planted_lint["violations"]}
    if "UNANCHORED_LOAD_BEARING" not in codes:
        print(f"FAILED:IMP-0214-probe1 expected UNANCHORED_LOAD_BEARING, got {codes}")
        return 1

    try:
        emit_rationale(
            workflow_id="wf.imp0214.should-refuse",
            goal="emitter must refuse a bare load-bearing decision",
            decisions=[
                {
                    "id": "D-bare",
                    "text": "We must adopt the adapter because it is fastest.",
                    "load_bearing": True,
                    "anchors": [],
                }
            ],
            root=REPO,
        )
    except ValueError as exc:
        print(f"emitter_refused_unanchored={exc.__class__.__name__}")
    else:
        print("FAILED:IMP-0214-probe1 emitter shipped an unanchored rationale")
        return 1

    emitted = emit_rationale(
        workflow_id=str(req.get("workflow_id") or "wf.imp0214.adopt"),
        goal=str(req.get("goal") or ""),
        decisions=list(req.get("decisions") or []),
        root=REPO,
        sources=list(req.get("sources") or []),
        benchmark_ledger=req.get("benchmark_ledger"),
    )
    good = lint_rationale(emitted, root=REPO)
    print("anchored", good["verdict"], "violation_count=", good["violation_count"])
    if not good["ok"] or good["verdict"] != PASS:
        print("FAILED:IMP-0214-probe1 fully anchored rationale did not pass")
        print(json.dumps(good, indent=2)[:2000])
        return 1
    if emitted.get("lint", {}).get("verdict") != PASS:
        print("FAILED:IMP-0214-probe1 emitter lint stamp missing")
        return 1

    mutant = copy.deepcopy(emitted)
    target = None
    for row in mutant["decisions"]:
        if row.get("id") == "D-adopt-entrypoint":
            row["anchors"] = []
            target = row
            break
    if target is None:
        print("FAILED:IMP-0214-probe1 missing D-adopt-entrypoint to strip")
        return 1
    stripped = lint_rationale(mutant, root=REPO)
    print(
        "stripped",
        stripped["verdict"],
        "codes=",
        sorted({v["code"] for v in stripped["violations"]}),
    )
    if stripped["ok"] or stripped["verdict"] != REJECTED:
        print("FAILED:IMP-0214-probe1 stripping anchors did not reject")
        return 1
    if not any(v.get("code") == "UNANCHORED_LOAD_BEARING" for v in stripped["violations"]):
        print("FAILED:IMP-0214-probe1 stripped mutant missing UNANCHORED_LOAD_BEARING")
        return 1

    print(
        "both_states planted_rejected=True anchored_pass=True "
        "strip_reverts_to_reject=True emitter_refuses_bare=True"
    )
    print("SUCCESS:IMP-0214-probe1 planted-rejected anchored-pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
