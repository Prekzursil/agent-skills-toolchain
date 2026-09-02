#!/usr/bin/env python3
"""Probe 1: gated project runs its declared command; absent file is NOT-CHECKED.

Mechanically independent of probe 2 (wrong-project isolation). Re-runs the
resolver live and compares the receipt rows to the live evaluation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0338.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0338-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "TST-0338":
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if "SUCCESS:TST-0338" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if S.artifact_has_aggregate_number(doc):
        return fail("artifact emits an aggregate coverage number")

    live = S.fixture_rows()
    gated = S.gated_absent_control(live)
    if not gated["with_file_command_ran"]:
        return fail("gated project did not run its declared command with reported exit code")
    if not gated["without_file_not_checked"]:
        return fail("ungated project was not NOT-CHECKED (pass/block/parent-trap leak)")

    alpha = live["alpha"]
    ungated = live["ungated"]
    if alpha.get("declared_command") != "python3 -B gate_alpha.py":
        return fail(f"alpha command {alpha.get('declared_command')!r}")
    if alpha.get("exit_code") != 0:
        return fail(f"alpha exit_code {alpha.get('exit_code')}")
    if ungated.get("result") != "NOT-CHECKED":
        return fail(f"ungated result {ungated.get('result')}")
    if ungated.get("pass") is True or ungated.get("blocked") is True:
        return fail("ungated folded into pass or block")

    rec_tests = doc.get("tests") or {}
    rec_with = rec_tests.get("project_with_file_runs_declared_command") or {}
    rec_abs = rec_tests.get("project_without_file_emits_not_checked") or {}
    if rec_with.get("pass") is not True:
        return fail("artifact with-file test not pass")
    if rec_with.get("exit_code") != alpha.get("exit_code"):
        return fail("artifact alpha exit_code != live")
    if rec_with.get("declared_command") != alpha.get("declared_command"):
        return fail("artifact alpha command != live")
    if rec_abs.get("pass") is not True:
        return fail("artifact absent-file test not pass")
    if rec_abs.get("result") != "NOT-CHECKED":
        return fail("artifact ungated result not NOT-CHECKED")
    if rec_abs.get("coverage_pass") is True or rec_abs.get("blocked") is True:
        return fail("artifact ungated pass/block")

    rec_ungated = ((doc.get("fixture_proof") or {}).get("ungated") or {})
    if rec_ungated.get("result") != "NOT-CHECKED":
        return fail("fixture_proof.ungated not NOT-CHECKED")
    trap = (doc.get("fixture_proof") or {}).get("parent_trap") or {}
    if trap.get("inherited_by_ungated") is not False:
        return fail("parent trap claimed inherited")

    out = {
        "probe": "probe1-gated-and-absent",
        "unit_id": "TST-0338",
        "alpha_exit_code": alpha.get("exit_code"),
        "alpha_command": alpha.get("declared_command"),
        "ungated_result": ungated.get("result"),
        "parent_trap_inherited": False,
        "aggregate_number": False,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"with_file={gated['with_file_command_ran']} "
        f"absent_not_checked={gated['without_file_not_checked']}"
    )
    print("SUCCESS:TST-0338-probe1 gated-command-ran and absent-NOT-CHECKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
