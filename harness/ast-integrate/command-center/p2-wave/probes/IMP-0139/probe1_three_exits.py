#!/usr/bin/env python3
"""Probe 1: three fixtures, three typed terminals, asserted in code."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.impossibility import ImpossibilityError, validate_impossibility  # noqa: E402
from agentspec.repair_loop import (  # noqa: E402
    AttemptLimitTerminal,
    PassedTerminal,
    ProvedImpossibleTerminal,
    run_fixture,
    terminal_as_dict,
)

UNIT = "IMP-0139"
ART = REPO / "command-center" / "receipts" / "IMP-0139.json"
FIXTURES = HERE / "fixtures"
SETTLING = "attach-macos-runner-then-recheck-health"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def receipt_ok() -> str:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt-missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return "receipt-unparseable"
    if not isinstance(doc, dict):
        return "receipt-not-object"
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{state}"
    if "SUCCESS:IMP-0139" not in text:
        return "sentinel-absent"
    return "ok"


def main() -> int:
    passed = run_fixture(_load("pass.json"))
    limited = run_fixture(_load("attempt_limit.json"))
    impossible = run_fixture(_load("impossibility.json"))

    types_ok = (
        isinstance(passed, PassedTerminal)
        and isinstance(limited, AttemptLimitTerminal)
        and isinstance(impossible, ProvedImpossibleTerminal)
        and type(passed) is not type(limited)
        and type(limited) is not type(impossible)
    )
    kinds = {passed.record_type, limited.record_type, impossible.record_type}
    kinds_ok = kinds == {
        "repair_passed",
        "repair_attempt_limit",
        "repair_proved_impossible",
    }
    limit_exhausted = (
        limited.attempts_used == limited.max_attempts == 2
        and limited.exhausted is True
    )
    impossible_early = impossible.attempts_used < impossible.max_attempts
    proof = validate_impossibility(impossible.proof)
    settling = proof["settling_experiment"]["id"]
    settling_ok = bool(settling) and settling == SETTLING

    search_rejected = False
    try:
        validate_impossibility(_load("invalid_search_failure.json"))
    except ImpossibilityError:
        search_rejected = True

    rec = receipt_ok()
    report = {
        "probe": "probe1-three-exits",
        "unit_id": UNIT,
        "passed": terminal_as_dict(passed),
        "attempt_limit": terminal_as_dict(limited),
        "proved_impossible": terminal_as_dict(impossible),
        "types_distinct": types_ok,
        "record_types": sorted(kinds),
        "kinds_ok": kinds_ok,
        "attempt_limit_exhausted": limit_exhausted,
        "impossibility_exited_before_limit": impossible_early,
        "settling_experiment_id": settling,
        "settling_experiment_named": settling_ok,
        "search_failure_rejected": search_rejected,
        "receipt": rec,
        "pass": False,
    }
    ok = (
        types_ok
        and kinds_ok
        and limit_exhausted
        and impossible_early
        and settling_ok
        and search_rejected
        and rec == "ok"
    )
    report["pass"] = ok
    print(json.dumps(report, indent=1, sort_keys=True))
    if not ok:
        print(f"FAILED:{UNIT}-probe1 three-exit discrimination")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe1 three fixtures -> three typed terminals; "
        f"settling_experiment={settling}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
