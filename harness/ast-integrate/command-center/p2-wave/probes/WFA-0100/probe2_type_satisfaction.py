#!/usr/bin/env python3
"""Probe 2: independent type checker + unsatisfiable INSERT refusal (both-states).

Evidence B. The checker lives in typecheck.py and does not emit fusions. An
operator that never refuses is coercing types silently. The coerce_splice
mutant still emits after rewriting the donor input type, so fusion-is-None
on the shipped path is a live detector.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    DONOR_INDEX,
    INSERT_INDEX,
    host_workflow,
    matching_donor,
    successor_mismatch_donor,
    unsatisfiable_donor,
)
from stage_splice import coerce_splice, stage_splice  # noqa: E402
from typecheck import REASON_UNSATISFIED_INPUT, insertion_type_check  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0100-fusion-stage-splice.json"


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0100-probe2 {msg}")
    return 1


def typecheck_imports() -> set[str]:
    tree = ast.parse((HERE / "typecheck.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.name or "").split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"artifact self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0100" not in text:
        return _fail("sentinel absent")

    imported = typecheck_imports()
    if "stage_splice" in imported:
        return _fail("typecheck.py imports stage_splice; checker is not independent")

    host = host_workflow()
    match = matching_donor()
    bad = unsatisfiable_donor()
    bad_succ = successor_mismatch_donor()

    check_good = insertion_type_check(host, match, INSERT_INDEX, DONOR_INDEX)
    check_bad = insertion_type_check(host, bad, INSERT_INDEX, DONOR_INDEX)
    if not check_good.get("ok"):
        return _fail(f"independent checker rejected a typed insertion: {check_good.get('reason')}")
    if check_bad.get("ok"):
        return _fail("independent checker accepted unsatisfiable pixels<-document")
    if check_bad.get("reason") != REASON_UNSATISFIED_INPUT:
        return _fail(f"bad-state reason {check_bad.get('reason')!r} is not unsatisfied-input-type")
    if check_bad.get("input_cover_ok") is not False:
        return _fail("checker did not fail input cover on pixels donor")
    missing = check_bad.get("missing_inputs") or []
    if not any(m.get("type") == "pixels" for m in missing):
        return _fail(f"missing_inputs {missing} did not name pixels")

    good = stage_splice(host, match, INSERT_INDEX, DONOR_INDEX)
    if good.get("status") != "emitted" or good.get("fusion") is None:
        return _fail(f"matching insert refused: {good.get('reason')}")

    refused = stage_splice(host, bad, INSERT_INDEX, DONOR_INDEX)
    if refused.get("status") != "refused" or refused.get("reason") != REASON_UNSATISFIED_INPUT:
        return _fail(f"unsatisfiable insert not refused: {refused.get('status')} {refused.get('reason')}")
    if refused.get("fusion") is not None:
        return _fail("unsatisfiable insert still emitted a fusion object")
    if refused.get("trace") != ["type-check", "refuse"]:
        return _fail(f"refusal trace {refused.get('trace')!r} is not check-then-refuse")

    refused_out = stage_splice(host, bad_succ, INSERT_INDEX, DONOR_INDEX)
    if refused_out.get("status") != "refused" or refused_out.get("fusion") is not None:
        return _fail("successor mismatch not refused")

    mutant = coerce_splice(host, bad, INSERT_INDEX, DONOR_INDEX)
    if mutant.get("fusion") is None or mutant.get("status") != "emitted":
        return _fail("coerce mutant did not emit (detector silent)")
    if mutant.get("coerced_input_type") == mutant.get("original_input_type"):
        return _fail("coerce mutant did not rewrite input type")
    # Independent checker still sees the ORIGINAL donor as unsatisfied.
    if insertion_type_check(host, bad, INSERT_INDEX, DONOR_INDEX).get("ok"):
        return _fail("checker flipped after coerce mutant; not independent")

    silent_on_good = check_good.get("ok") is True and good.get("status") == "emitted"
    fires_on_bad = check_bad.get("ok") is False and refused.get("status") == "refused"
    if not (silent_on_good and fires_on_bad):
        return _fail("both-states control did not discriminate")

    summary = {
        "probe": "probe2-type-satisfaction",
        "unit_id": "WFA-0100",
        "pass": True,
        "checker_independent": True,
        "matching_accepted": True,
        "unsatisfiable_refused": True,
        "shipped_fusion_none_on_unsat": True,
        "mutant_fusion_present_on_unsat": True,
        "successor_mismatch_refused": True,
        "silent_on_good": silent_on_good,
        "fires_on_bad": fires_on_bad,
        "missing_inputs": missing,
        "shipped_trace_good": good.get("trace"),
        "shipped_trace_bad": refused.get("trace"),
        "mutant_trace": mutant.get("trace"),
        "producer_type": check_bad.get("producer_type"),
        "unsat_donor_input_type": check_bad.get("donor_input_type"),
        "typecheck_imports": sorted(imported),
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:WFA-0100-probe2 independent typecheck refused unsatisfiable insert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
