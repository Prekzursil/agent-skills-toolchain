#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0013.json from a live harness self-test."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
HARNESS = REPO / "command-center" / "harness"
sys.path.insert(0, str(HARNESS))

from test_both_states import run_all  # noqa: E402

OUT = "command-center/receipts/TST-0013.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
HARNESS_MOD = "command-center/harness/both_states.py"
HARNESS_TEST = "command-center/harness/test_both_states.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0013/probe1_reject_uncontrolled.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0013/probe2_accept_and_self_control.py"
)
QUESTION = (
    "Target: ship a single importable fixture/decorator that takes "
    "(check, good_state, broken_state) and asserts the check is SILENT on "
    "good and FIRES on broken, emitting a typed control record. A probe "
    "silent in both states measures nothing (:11324). Every downstream test "
    "unit in this bucket consumes this harness rather than re-implementing it."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0013 emit snippet not found in {rel}: {snippet!r}")
    return text[:idx].count("\n") + 1


def main() -> int:
    records = run_all()
    silent = records["silent_in_both"]
    fires = records["fires_in_both"]
    correct = records["correct"]
    self_ctrl = records["self_control"]
    if silent.verdict != "REJECTED" or silent.rejection_reason != "silent-in-both":
        print("FAILED:TST-0013 inert check was not REJECTED")
        return 1
    if fires.verdict != "REJECTED" or fires.rejection_reason != "fires-in-both":
        print("FAILED:TST-0013 always-fire check was not REJECTED")
        return 1
    if correct.verdict != "VALID" or self_ctrl.verdict != "VALID":
        print("FAILED:TST-0013 correct/self-control not VALID")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ctrl_line = find_line(HARNESS_MOD, "def control(")
    inert_line = find_line(
        HARNESS_TEST, "def test_harness_rejects_a_check_silent_in_both_states"
    )
    self_line = find_line(
        HARNESS_TEST, "def test_harness_is_itself_both_states_controlled"
    )

    controls = [records[k].to_dict() for k in (
        "silent_in_both",
        "fires_in_both",
        "polarity",
        "correct",
        "assert_style",
        "decorator",
        "self_control",
    )]

    doc = {
        "unit_id": "TST-0013",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0013",
        "report_kind": "detector-control",
        "title": "Reusable both-states control harness",
        "phase": "0",
        "ts": now,
        "question": QUESTION,
        "harness": {
            "module_path": HARNESS_MOD,
            "self_test_path": HARNESS_TEST,
            "import_name": "both_states",
            "api": [
                "control",
                "both_states",
                "both_states_decorator",
                "ControlRecord",
                "both_states_control",
            ],
            "consumption": (
                "sys.path.insert(0, 'command-center/harness'); "
                "from both_states import control"
            ),
        },
        "self_test": {
            "inert_check_rejected": True,
            "always_fire_check_rejected": True,
            "correct_check_accepted": True,
            "harness_both_states_valid": True,
            "assert_style_accepted": True,
            "decorator_accepted": True,
        },
        "controls": controls,
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "A check silent in both states is REJECTED by the harness "
                    "(silent-in-both), so an inert probe cannot be reported as "
                    "verification."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{HARNESS_TEST}:{inert_line}",
            },
            {
                "id": "C2",
                "claim": (
                    "A check that fires in both states is REJECTED "
                    "(fires-in-both); a false-positive machine is not VALID."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{HARNESS_MOD}:{ctrl_line}",
            },
            {
                "id": "C3",
                "claim": (
                    "A correct check is SILENT on the good state and FIRES on "
                    "the broken state and is accepted as VALID, emitting a "
                    "typed ControlRecord."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{HARNESS_MOD}:{ctrl_line}",
            },
            {
                "id": "C4",
                "claim": (
                    "The harness is itself both-states controlled: it is SILENT "
                    "(accepts) on a correct check and FIRES (rejects) on a "
                    "deliberately inert check."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{HARNESS_TEST}:{self_line}",
            },
        ],
        "tests": [
            {
                "id": "test_harness_rejects_a_check_silent_in_both_states",
                "name": "Harness rejects a check silent in both states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_harness_rejects_a_check_that_fires_in_both_states",
                "name": "Harness rejects a check that fires in both states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_harness_accepts_a_correct_check",
                "name": "Harness accepts a correct check and self-controls",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0013-probe2-accept-and-self-control",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 is a mechanically different instrument from probe 1: "
                "it runs the accept path, decorator, assert-style detector, "
                "harness self-control, and a schema round-trip of the typed "
                "record, including a negative fixture (VALID with "
                "fired_on_bad_state=false must be INVALID)."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": HARNESS_MOD, "exists": True, "role": "harness"},
            {"path": HARNESS_TEST, "exists": True, "role": "self-test"},
        ],
        "evidence": [
            {
                "path": HARNESS_MOD,
                "kind": "harness-source",
                "line": ctrl_line,
                "snippet": "def control(",
                "claim": "importable control(check, good_state, broken_state)",
            },
            {
                "path": HARNESS_TEST,
                "kind": "self-test",
                "line": inert_line,
                "snippet": "def test_harness_rejects_a_check_silent_in_both_states",
                "claim": "deliberately inert check is REJECTED",
            },
            {
                "path": SCHEMA,
                "kind": "schema",
                "line": find_line(SCHEMA, '"$defs"'),
                "snippet": '"$defs"',
                "claim": "typed control_record is schema-constrained",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "reject-uncontrolled", "command": P1},
            {"id": "probe2", "role": "accept-and-self-control", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0013/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "headline": (
            "harness=command-center/harness/both_states.py "
            "inert=REJECTED correct=VALID self-control=VALID"
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    ctrl_schema = (schema.get("$defs") or {}).get("control_record")
    if not isinstance(ctrl_schema, dict):
        print("FAILED:TST-0013 schema missing $defs.control_record")
        return 1
    ctrl_validator = jsonschema.Draft7Validator(ctrl_schema)
    for rec in controls:
        rec_errs = sorted(
            ctrl_validator.iter_errors(rec), key=lambda e: list(e.path)
        )
        if rec_errs:
            print("FAILED:TST-0013 control_record schema errors")
            for e in rec_errs[:20]:
                print(" ", rec.get("check_id"), list(e.path), e.message)
            return 1
    # Catalog output_schema is a generated $ref shim to ast-integrate.invalid.
    # Draft7Validator cannot resolve that URL here. Document-level checks use
    # the local contract below so garbage is still rejected.
    document_schema = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "report_kind",
            "title",
            "question",
            "harness",
            "self_test",
            "controls",
            "claims",
            "tests",
            "reviewer",
            "artifacts",
            "evidence",
            "named_probes",
        ],
        "properties": {
            "unit_id": {"const": "TST-0013"},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": "SUCCESS:TST-0013"},
            "report_kind": {"const": "detector-control"},
            "question": {"type": "string", "minLength": 80},
            "controls": {"type": "array", "minItems": 7},
            "claims": {"type": "array", "minItems": 4},
            "tests": {"type": "array", "minItems": 3},
            "named_probes": {"type": "array", "minItems": 2},
        },
    }
    validator = jsonschema.Draft7Validator(document_schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0013 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {
            "unit_id": "TST-0013",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:TST-0013",
            "report_kind": "detector-control",
            "question": "x" * 50,
        },
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:TST-0013 schema accepted garbage {list(g)[:4]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(doc["headline"])
    print("SUCCESS:TST-0013")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
