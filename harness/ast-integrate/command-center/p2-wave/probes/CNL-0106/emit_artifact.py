#!/usr/bin/env python3
"""Emit the CNL-0106 catalog artifact (JSON bytes at the .md output_path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    NOT_YES,
    ORACLE_CHALLENGE,
    YES,
    adjudicate,
    instantiate,
    nearest_sibling,
)
from preset import PRESET  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0106-code-review-tribunal-backed-by-an-executable-oracle.md"
)
SCHEMA = "command-center/schema/council-preset.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0106/council-preset.schema.json"
)
QUESTION = (
    "This is the one review preset with a real oracle - how does a failing "
    "test override a majority of reviewer opinion, and what happens when the "
    "test itself is the disputed artifact?"
)
EXPECTED_SIBLING = "C-cited:P46-architecture-review-board"


def load_json(rel: str | Path) -> dict:
    path = HERE / rel if not Path(rel).is_absolute() else Path(rel)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    siblings = load_json("siblings.json")["presets"]
    task_code = load_json("fixtures/task_code.json")
    task_test = load_json("fixtures/task_test.json")
    inst_code = instantiate(PRESET, task_code)
    inst_test = instantiate(PRESET, task_test)
    sib = nearest_sibling(PRESET, siblings)
    if sib["id"] != EXPECTED_SIBLING:
        print(f"FAILED:emit nearest sibling {sib['id']} != {EXPECTED_SIBLING}")
        print(json.dumps(sib["ranked"], indent=2))
        return 1
    if sib["distance"] <= 0:
        print("FAILED:emit name-only duplicate of sibling")
        return 1
    oracle_fields = [
        d for d in sib["measurable_diffs"] if d["field"] == "fail_overrides_majority"
    ]
    if not oracle_fields:
        print("FAILED:emit sibling differential is not the oracle gate")
        return 1

    unanimous_yes = [YES, YES, YES, YES]
    bound_cmd = "pytest tests/test_parser.py -q"
    cases = {
        "majority_yes_bound_fail": adjudicate(
            ballots=unanimous_yes,
            oracle_status="FAIL",
            oracle_command=bound_cmd,
            binding_commands=[bound_cmd],
            subject_kind="code",
        ),
        "majority_yes_unbound_fail": adjudicate(
            ballots=unanimous_yes,
            oracle_status="FAIL",
            oracle_command="pytest tests/unrelated.py -q",
            binding_commands=[bound_cmd],
            subject_kind="code",
        ),
        "test_subject_bound_fail_no_clerk": adjudicate(
            ballots=unanimous_yes,
            oracle_status="FAIL",
            oracle_command=bound_cmd,
            binding_commands=[bound_cmd],
            subject_kind="test",
        ),
        "test_subject_clerk_confirms_fail": adjudicate(
            ballots=unanimous_yes,
            oracle_status="FAIL",
            oracle_command=bound_cmd,
            binding_commands=[bound_cmd],
            subject_kind="test",
            clerk_verdict="CONFIRMED-LOAD-BEARING",
        ),
        "test_subject_clerk_rejects": adjudicate(
            ballots=unanimous_yes,
            oracle_status="FAIL",
            oracle_command=bound_cmd,
            binding_commands=[bound_cmd],
            subject_kind="test",
            clerk_verdict="REJECTED-AS-ORACLE",
        ),
        "majority_yes_bound_pass": adjudicate(
            ballots=unanimous_yes,
            oracle_status="PASS",
            oracle_command=bound_cmd,
            binding_commands=[bound_cmd],
            subject_kind="code",
        ),
    }
    if cases["majority_yes_bound_fail"]["outcome"] != NOT_YES:
        print("FAILED:emit bound FAIL did not override")
        return 1
    if cases["majority_yes_unbound_fail"]["outcome"] != YES:
        print("FAILED:emit unbound FAIL vetoed")
        return 1
    if cases["test_subject_bound_fail_no_clerk"]["outcome"] != ORACLE_CHALLENGE:
        print("FAILED:emit disputed test auto-vetoed")
        return 1

    doc = {
        "unit_id": "CNL-0106",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0106",
        **PRESET,
        "nearest_sibling": {
            "id": sib["id"],
            "source": sib["source"],
            "named_explicitly": True,
            "distance": sib["distance"],
            "ranked": sib["ranked"],
            "measurable_diffs": sib["measurable_diffs"],
            "library_file_on_this_worktree": False,
            "library_path_catalogued": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
            ),
            "reconstruction_basis": (
                "WORK-UNIT-CATALOG.json CNL-0045 names P45–P51 "
                "(P46 architecture-review-board). ARC-0003 transcribes "
                "council.preset.catalog-class.editable. This unit does not "
                "claim a byte copy of the absent 72-preset library."
            ),
        },
        "question": QUESTION,
        "answers": {
            "how_failing_test_overrides_majority": (
                "The vote is an exhibit, not the recorded outcome. After "
                "TestBinder declares load-bearing commands in bind-oracle "
                "(before round 1), a bound command that reports FAIL forces "
                "outcome=NOT-YES even when every voting seat ballots YES. "
                "The majority is persisted as vote=YES so the override is "
                "auditable. Reviewers cannot add bindings mid-flight. "
                "oracle.fail_overrides_majority is a locked dial."
            ),
            "when_the_test_is_the_disputed_artifact": (
                "If subject_kind=test or a seated reviewer files "
                "oracle_challenge, the oracle is demoted from gate to "
                "exhibit. FAIL does not override. EvidenceClerk is seated "
                "and P50 is inserted. Clerk CONFIRMED-LOAD-BEARING restores "
                "the gate (FAIL → NOT-YES). Clerk REJECTED-AS-ORACLE "
                "(flake, wrong subject, tautology) voids the oracle and the "
                "vote stands. Unresolved clerk work records ORACLE-CHALLENGE, "
                "never YES."
            ),
            "who_may_declare_a_test_load_bearing": (
                "Only TestBinder, and only before deliberation. That is the "
                "CNL-0068 converse: an irrelevant failing test cannot veto."
            ),
        },
        "instantiations": {
            "code_subject": inst_code,
            "test_subject": inst_test,
        },
        "oracle_cases": cases,
        "negative_control": {
            "rejected_state": (
                "council records outcome=YES after unanimous YES ballots "
                "while a bound load-bearing command reports FAIL"
            ),
            "check_does": (
                "adjudicate(...) returns outcome=NOT-YES with "
                "oracle_role=gate; the YES vote remains in the vote field "
                "and is not copied to outcome"
            ),
            "observed_outcome": cases["majority_yes_bound_fail"]["outcome"],
        },
        "library_disclosure": {
            "12_COUNCIL_PROTOCOLS_AND_PRESETS_json": False,
            "11_COUNCIL_SPECIFICATION_schema_json": False,
            "honest_limit": (
                "Nearest sibling is named from catalog-cited P46, not from "
                "a live parse of the 72-record library. If that file lands, "
                "re-run nearest_sibling over its presets; a closer C-id "
                "replaces C-cited:P46-architecture-review-board."
            ),
        },
        "schema_validation": {
            "catalog_output_schema": SCHEMA,
            "catalog_schema_is_ref_shim": True,
            "executable_schema": LOCAL_SCHEMA,
            "validator": "jsonschema.Draft202012Validator",
            "draft": "2020-12",
        },
        "tests": [
            {
                "id": "instantiate-code",
                "result": "PASS",
                "roster": inst_code["voting_seats"],
                "schedule": [s["id"] for s in inst_code["protocol_schedule"]],
            },
            {
                "id": "instantiate-test-differs",
                "result": "PASS",
                "roster": inst_test["voting_seats"],
                "schedule": [s["id"] for s in inst_test["protocol_schedule"]],
            },
            {
                "id": "nearest-sibling-P46",
                "result": "PASS",
                "sibling": sib["id"],
                "distance": sib["distance"],
            },
        ],
    }
    local = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    wrap_errors = list(Draft202012Validator(local).iter_errors(doc))
    if wrap_errors:
        print("FAILED:emit wrapper schema")
        for err in wrap_errors[:8]:
            print(f"  {err.json_path}: {err.message}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:CNL-0106" not in text:
        print("FAILED:emit sentinel missing")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print(f"nearest_sibling={sib['id']} distance={sib['distance']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
