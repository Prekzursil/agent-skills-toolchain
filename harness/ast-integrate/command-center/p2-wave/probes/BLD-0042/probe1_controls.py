#!/usr/bin/env python3
"""Probe 1: three catalog controls plus schema/sentinel on the live receipt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import constants as K  # noqa: E402
import validate_schema as V  # noqa: E402
from fixtures import planted_defaults as P  # noqa: E402

ART = REPO / K.OUT_REL


def main() -> int:
    P.run_planted_assertions()
    P.run_empty_test_only()
    measured = C.run_census()
    controls = C.control_results(measured)
    required = controls[:3]
    print(json.dumps(required, sort_keys=True))
    if any(c["result"] != "PASS" for c in required):
        print("FAILED:BLD-0042-probe1 controls")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0042-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if K.SENTINEL not in text:
        print("FAILED:BLD-0042-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:BLD-0042-probe1 self-declared {doc.get('state')}")
        return 1
    if not V.garbage_rejected():
        print("FAILED:BLD-0042-probe1 schema vacuous")
        return 1
    errs = V.validate_doc(doc)
    if errs:
        print("FAILED:BLD-0042-probe1 schema")
        print("\n".join(errs[:8]))
        return 1
    unex = ((doc.get("census") or {}).get("unexercised")) or []
    names = {row.get("name") for row in unex if isinstance(row, dict)}
    if "require_complete" not in names:
        print("FAILED:BLD-0042-probe1 require_complete missing from unexercised")
        return 1
    if "flag" in names and any(
        r.get("func_name") == "planted_exercised" for r in unex if isinstance(r, dict)
    ):
        print("FAILED:BLD-0042-probe1 planted_exercised wrongly reported")
        return 1
    for row in unex:
        if not isinstance(row, dict):
            continue
        if row.get("func_name") == "planted_exercised":
            print("FAILED:BLD-0042-probe1 planted_exercised in unexercised list")
            return 1
    ci = (doc.get("census") or {}).get("ci_join") or {}
    invocations = int(
        ci.get("validate_py_invocations")
        or ci.get("validate_py_invocations")
        or 0
    )
    flag_passed = int(
        ci.get("require_complete_flag_passed")
        or ci.get("require_complete_flag_passed")
        or 0
    )
    if invocations < 1:
        print("FAILED:BLD-0042-probe1 no CI validate.py invocation")
        return 1
    if flag_passed != 0:
        print("FAILED:BLD-0042-probe1 CI unexpectedly passes --require-complete")
        return 1
    print(
        "require_complete_unexercised=True planted_exercised_excluded=True "
        f"ci_bare=True invocations={invocations}"
    )
    print("SUCCESS:BLD-0042-probe1 default-exercise controls and CI join")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
