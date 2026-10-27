#!/usr/bin/env python3
"""REFUTE-GATE-BYPASSES: the gate must REJECT every recorded bypass.

The refute-stage receipt (D04) recorded three live bypasses against the
implementation gate. Each is replayed here and must now be REJECTED; the
negative control (a genuinely bound RUN) must still PASS. Exit 0 only when
every bypass is rejected and the negative control is accepted.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage_gate as G  # noqa: E402
import test_coverage_gate as T  # noqa: E402

DECLARED = ["claude-code", "codex-cli", "antigravity-agy"]


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def bypass_forged_unrelated_receipt() -> None:
    """Bypass 1: a RUN whose evidence cites an unrelated unit's receipt."""
    forged = copy.deepcopy(T.INSIDE)
    forged["suite_id"] = ""
    forged["evidence"]["receipt"] = "command-center/receipts/BLD-0001.json"
    errs = G.validate_cell(forged)
    _assert(
        "RUN-evidence-not-bound-to-TST-0049" in errs,
        f"BYPASS-1 ACCEPTED (forged unrelated-receipt RUN): {errs}",
    )
    print("bypass-1 forged-unrelated-receipt RUN -> rejected")


def bypass_wrong_suite_object() -> None:
    """Bypass 2: a RUN bound to the wrong suite id."""
    wrong = copy.deepcopy(T.INSIDE)
    wrong["suite_id"] = "TST-0048"
    errs = G.validate_cell(wrong)
    _assert(
        "RUN-evidence-not-bound-to-TST-0049" in errs,
        f"BYPASS-2 ACCEPTED (wrong-suite RUN): {errs}",
    )
    print("bypass-2 wrong-suite RUN -> rejected")


def bypass_incomplete_matrix() -> None:
    """Bypass 3: a matrix silently missing a declared client."""
    cells = [
        {"id": "claude-code x hook-fires", "client_id": "claude-code"},
        {"id": "codex-cli x hook-fires", "client_id": "codex-cli"},
    ]
    findings = G.check_declared_coverage(cells, DECLARED)
    _assert(
        findings == ["declared-client-absent-from-matrix:antigravity-agy"],
        f"BYPASS-3 ACCEPTED (incomplete matrix): {findings}",
    )
    print("bypass-3 incomplete matrix -> rejected")


def negative_control_good_run() -> None:
    """Negative control: a well-formed bound RUN must NOT be flagged."""
    _assert(G.validate_cell(T.INSIDE) == [], "negative control flagged")
    _assert(G.classify(T.INSIDE) == "RUN", "negative control misclassified")
    print("negative-control bound RUN with version+inside-obs -> accepted")


def main() -> int:
    checks = [
        bypass_forged_unrelated_receipt,
        bypass_wrong_suite_object,
        bypass_incomplete_matrix,
        negative_control_good_run,
    ]
    failed = 0
    for fn in checks:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    if failed:
        print(f"FAILED:BLD-0006-refute {failed}/{len(checks)} checks failed")
        return 1
    print(f"SUCCESS:BLD-0006-refute {len(checks)} checks passed (3 bypasses rejected, 1 negative control clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
