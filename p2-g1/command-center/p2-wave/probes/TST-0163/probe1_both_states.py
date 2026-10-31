#!/usr/bin/env python3
"""Probe 1: both-states control — unedited is silent; mid-run edit is CONTRACT-DRIFT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0163.json"
UNIT = "TST-0163"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0163" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    unedited = S.test_unedited_reports_no_drift()
    drift = S.test_midrun_cap_edit_is_contract_drift()
    payload = {
        "probe": "probe1-both-states",
        "unit_id": UNIT,
        "pass": unedited["pass"] and drift["pass"],
        "unedited_result": unedited.get("result"),
        "unedited_n_drifted": unedited.get("n_drifted"),
        "unedited_caps": unedited.get("caps_observed"),
        "unedited_pids_distinct": unedited.get("pids_distinct"),
        "drift_result": drift.get("result"),
        "drift_n_drifted": drift.get("n_drifted"),
        "drift_named_hashes": drift.get("named_hashes"),
        "drift_caps": drift.get("caps_observed"),
        "kinds": drift.get("kinds"),
        "both_states": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"unedited={unedited.get('result')} n_drifted={unedited.get('n_drifted')} "
        f"edit={drift.get('result')} named={drift.get('named_hashes')} "
        f"caps={drift.get('caps_observed')}"
    )
    if not unedited["pass"]:
        return fail("unedited run was not silent")
    if unedited.get("result") != "OK" or unedited.get("n_drifted") != 0:
        return fail("unedited did not report OK/no-drift")
    if not drift["pass"]:
        return fail("mid-run cap edit was not typed CONTRACT-DRIFT")
    if drift.get("result") != "CONTRACT-DRIFT":
        return fail(f"drift result {drift.get('result')}")
    named = drift.get("named_hashes") or {}
    if not named.get("dispatch") or not named.get("fanin"):
        return fail("CONTRACT-DRIFT did not name both hashes")
    if named["dispatch"] == named["fanin"]:
        return fail("named hashes were equal after a live edit")
    if drift.get("caps_observed") != [S.CAP_BEFORE, S.CAP_AFTER]:
        return fail("contradictory caps not observed on the edited run")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "test_unedited_reports_no_drift",
        "test_midrun_cap_edit_is_contract_drift",
    ):
        row = tests.get(tid)
        if not row or row.get("result") != "PASS":
            return fail(f"receipt missing PASS for {tid}")
    both = doc.get("both_states") or {}
    if both.get("unedited_silent") is not True or both.get("edited_drift") is not True:
        return fail("receipt both_states drift")

    print("SUCCESS:TST-0163-probe1 unedited silent; mid-run edit is CONTRACT-DRIFT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
