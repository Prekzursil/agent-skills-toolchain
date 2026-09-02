#!/usr/bin/env python3
"""Probe 2: harness ACCEPTS a correct check; harness is both-states controlled.

Mechanically different from probe 1: this probe runs the accept path, the
decorator form, an assert-style detector, the harness self-control (inert
check REJECTED / correct check accepted), and a schema round-trip of the
typed record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[4]
HARNESS = REPO / "command-center" / "harness"
sys.path.insert(0, str(HARNESS))

from test_both_states import (  # noqa: E402
    test_decorator_form_accepts_correct_check,
    test_harness_accepts_a_correct_check,
    test_harness_accepts_assert_style_check,
    test_harness_is_itself_both_states_controlled,
)

SCHEMA = REPO / "command-center" / "schema" / "detector-control.schema.json"


def _schema_roundtrip(record_dict: dict) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema["$defs"]["control_record"])
    errs = sorted(validator.iter_errors(record_dict), key=lambda e: list(e.path))
    if errs:
        raise AssertionError(
            "VALID control record failed schema: "
            + "; ".join(e.message for e in errs[:8])
        )
    broken = dict(record_dict)
    broken["fired_on_bad_state"] = False
    broken["verdict"] = "VALID"
    if not list(jsonschema.Draft7Validator(schema["$defs"]["control_record"]).iter_errors(broken)):
        raise AssertionError("schema accepted VALID with fired_on_bad_state=false")


def main() -> int:
    correct = test_harness_accepts_a_correct_check()
    assert_style = test_harness_accepts_assert_style_check()
    decorated = test_decorator_form_accepts_correct_check()
    self_ctrl = test_harness_is_itself_both_states_controlled()
    _schema_roundtrip(correct.to_dict())
    print(
        f"correct verdict={correct.verdict} "
        f"good={correct.good_outcome} broken={correct.broken_outcome}"
    )
    print(f"assert_style verdict={assert_style.verdict}")
    print(f"decorator verdict={decorated.verdict} id={decorated.check_id}")
    print(
        f"self_control verdict={self_ctrl.verdict} "
        f"fired_on_inert={self_ctrl.fired_on_bad_state} "
        f"silent_on_correct={self_ctrl.silent_on_good_state}"
    )
    print("schema_roundtrip=True")
    if not all(
        rec.verdict == "VALID"
        for rec in (correct, assert_style, decorated, self_ctrl)
    ):
        print("FAILED:TST-0013-probe2 expected four VALID records")
        return 1
    print(
        "SUCCESS:TST-0013-probe2 accepts correct check; "
        "harness both-states self-control VALID"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
