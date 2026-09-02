#!/usr/bin/env python3
"""Seeded three-independent-defect job plus one genuine dependent (TST-0016).

Defect classes match this estate's mutation vocabulary (JSON key-case,
LF→CRLF, sentinel deletion). The dependent step consumes the JSON
check's normalized output and MUST short-circuit when that check is red.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aggregate import Outcome, StepSpec, run_job  # noqa: E402

DEFECT_JSON = "DEFECT-JSON-KEY-CASE"
DEFECT_CRLF = "DEFECT-LF-CRLF"
DEFECT_SENTINEL = "DEFECT-SENTINEL-DELETED"
SETUP_ID = "setup-workdir"
JSON_ID = "check-json-key-case"
CRLF_ID = "check-lf-crlf"
SENTINEL_ID = "check-sentinel-present"
CONSUME_ID = "publish-normalized-json"


def _specs(fail: set[str]) -> list[StepSpec]:
    def setup() -> Outcome:
        return Outcome(0, [], note="workdir ready")

    def json_check() -> Outcome:
        if JSON_ID in fail:
            return Outcome(1, [DEFECT_JSON], note="key Case flipped")
        return Outcome(0, [], note="json keys stable")

    def crlf_check() -> Outcome:
        if CRLF_ID in fail:
            return Outcome(1, [DEFECT_CRLF], note="LF became CRLF")
        return Outcome(0, [], note="LF preserved")

    def sentinel_check() -> Outcome:
        if SENTINEL_ID in fail:
            return Outcome(1, [DEFECT_SENTINEL], note="sentinel deleted")
        return Outcome(0, [], note="sentinel present")

    def consume() -> Outcome:
        return Outcome(0, [], note="published json from check-json-key-case")

    return [
        StepSpec(SETUP_ID, (), setup, kind="setup"),
        StepSpec(JSON_ID, (SETUP_ID,), json_check, kind="check"),
        StepSpec(CRLF_ID, (SETUP_ID,), crlf_check, kind="check"),
        StepSpec(SENTINEL_ID, (SETUP_ID,), sentinel_check, kind="check"),
        StepSpec(CONSUME_ID, (JSON_ID,), consume, kind="check"),
    ]


THREE = {JSON_ID, CRLF_ID, SENTINEL_ID}


def test_three_seeded_independent_defects_are_all_reported_in_one_run() -> dict:
    ff = run_job(_specs(THREE), "fail_fast")
    ag = run_job(_specs(THREE), "aggregate")
    ok = (
        set(ag.defects) == {DEFECT_JSON, DEFECT_CRLF, DEFECT_SENTINEL}
        and ff.defects == [DEFECT_JSON]
        and len(ff.skipped_fail_fast()) >= 3
        and {r.id for r in ag.executed()} >= {JSON_ID, CRLF_ID, SENTINEL_ID}
    )
    return {
        "id": "test_three_seeded_independent_defects_are_all_reported_in_one_run",
        "result": "PASS" if ok else "FAIL",
        "fail_fast": ff.as_dict(),
        "aggregate": ag.as_dict(),
        "observable": {
            "kind": "process-visible-effect",
            "reads": "aggregate.defects vs fail_fast.defects",
            "distinct_from_file_existence": True,
            "fail_fast_defect_count": len(ff.defects),
            "aggregate_defect_count": len(ag.defects),
        },
    }


def test_a_genuinely_dependent_step_still_short_circuits() -> dict:
    ag = run_job(_specs(THREE), "aggregate")
    consume = next(r for r in ag.results if r.id == CONSUME_ID)
    ok = (
        consume.status == "skipped-dependency"
        and JSON_ID in (consume.note or "")
        and consume.exit_code is None
    )
    green = run_job(_specs(set()), "aggregate")
    consume_ok = next(r for r in green.results if r.id == CONSUME_ID)
    ok = ok and consume_ok.status == "executed" and consume_ok.exit_code == 0
    return {
        "id": "test_a_genuinely_dependent_step_still_short_circuits",
        "result": "PASS" if ok else "FAIL",
        "three_red_consume": {
            "status": consume.status,
            "note": consume.note,
        },
        "all_green_consume": {
            "status": consume_ok.status,
            "exit_code": consume_ok.exit_code,
        },
    }


def test_aggregate_exit_code_is_red_when_any_check_is_red() -> dict:
    three = run_job(_specs(THREE), "aggregate")
    one = run_job(_specs({CRLF_ID}), "aggregate")
    none = run_job(_specs(set()), "aggregate")
    ok = three.exit_code == 1 and one.exit_code == 1 and none.exit_code == 0
    ok = ok and one.defects == [DEFECT_CRLF]
    consume = next(r for r in one.results if r.id == CONSUME_ID)
    ok = ok and consume.status == "executed"
    return {
        "id": "test_aggregate_exit_code_is_red_when_any_check_is_red",
        "result": "PASS" if ok else "FAIL",
        "three_red_exit": three.exit_code,
        "one_red_exit": one.exit_code,
        "all_green_exit": none.exit_code,
        "one_red_defects": list(one.defects),
        "one_red_consume_status": consume.status,
    }


def run_required_tests() -> list[dict]:
    return [
        test_three_seeded_independent_defects_are_all_reported_in_one_run(),
        test_a_genuinely_dependent_step_still_short_circuits(),
        test_aggregate_exit_code_is_red_when_any_check_is_red(),
    ]
