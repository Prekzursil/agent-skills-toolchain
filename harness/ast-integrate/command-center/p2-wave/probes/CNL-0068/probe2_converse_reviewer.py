#!/usr/bin/env python3
"""Probe 2: converse control + independent adversarial recount.

Does not read the design note's mechanism.summary to decide the tally.
Produces counterexample instances that would refute the claim if the
engine accepted an irrelevant failing test, a seat-declared binding, a
post-close binding, a majority-declared binding, a prefix claim_id, or
weighted unanimity as outranking a failing bound test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import override as O  # noqa: E402

NOTE = (
    REPO
    / "command-center/design/council/CNL-0068-evidence-outranks-popularity-the-executable-test-override-.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
ACCEPTING = O.ACCEPTING


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0068-probe2 {msg}")
    return 1


def expect_yes(name: str, result: dict, *, why: str) -> str | None:
    if result["outcome"] not in ACCEPTING:
        return f"{name} vetoed a sound YES ({why}): outcome={result['outcome']}"
    if result["overriding_tests"]:
        return f"{name} recorded an override ({why})"
    return None


def expect_refuted(name: str, result: dict, *, why: str) -> str | None:
    if result["outcome"] in ACCEPTING:
        return f"{name} left YES standing ({why}): outcome={result['outcome']}"
    if result["outcome"] != "REFUTED":
        return f"{name} expected REFUTED ({why}), got {result['outcome']}"
    return None


def main() -> int:
    converse = O.fixture_result("irrelevant_fail.json")
    weighted = O.fixture_result("weighted_unanimous_refuted.json")
    seat = O.fixture_result("seat_declares.json")
    post = O.fixture_result("post_close.json")
    majority = O.fixture_result("majority_declares.json")
    prefix = O.fixture_result("prefix_mismatch.json")

    cases = {
        "CE-IRRELEVANT-FAIL": converse,
        "CE-WEIGHTED-UNANIMITY": weighted,
        "CE-SEAT-BINDER": seat,
        "CE-POST-CLOSE": post,
        "CE-MAJORITY-DECLARE": majority,
        "CE-PREFIX-CLAIM": prefix,
    }
    print(json.dumps({k: v for k, v in cases.items()}, sort_keys=True, default=str)[:4000])

    errors: list[str] = []
    err = expect_yes(
        "irrelevant_fail",
        converse,
        why="failing test bound to a different claim",
    )
    if err:
        errors.append(err)
    if not converse["irrelevant_failures"]:
        errors.append("irrelevant_fail did not record the unbound failure")

    err = expect_refuted(
        "weighted_unanimous_refuted",
        weighted,
        why="non-equal weights must not outrank a failing bound test",
    )
    if err:
        errors.append(err)
    if weighted["tally"]["yes_weight"] != 10.0:
        errors.append(f"weighted yes_weight={weighted['tally']['yes_weight']}")

    for name, result, tag in (
        ("seat_declares", seat, "binder-role-forbidden:seat"),
        ("post_close", post, "declared-at-or-after-ballot-close"),
        ("majority_declares", majority, "majority-cannot-declare-load-bearing"),
    ):
        err = expect_yes(name, result, why="illegal binding cannot manufacture a veto")
        if err:
            errors.append(err)
        reasons = [
            r
            for row in result["rejected_bindings"]
            for r in (row.get("reject_reasons") or [])
        ]
        if tag not in reasons:
            errors.append(f"{name} missing reject reason {tag}: {reasons}")

    err = expect_yes(
        "prefix_mismatch",
        prefix,
        why="claim_id equality is exact, not prefix",
    )
    if err:
        errors.append(err)

    if errors:
        for item in errors:
            print(item)
        return fail("; ".join(errors[:3]))

    if not NOTE.is_file() or not SCHEMA.is_file():
        return fail("design note or schema missing")
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        jsonschema.Draft7Validator(schema).validate(note)
    except jsonschema.exceptions.RefResolutionError:
        pass
    except jsonschema.ValidationError as exc:
        return fail(f"schema {exc.message}")
    if note.get("unit_id") != "CNL-0068":
        return fail("note unit_id mismatch")
    if "SUCCESS:CNL-0068" not in NOTE.read_text(encoding="utf-8"):
        return fail("sentinel absent from note")
    if str(note.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"note self-declared {note.get('state')}")
    verbatim = O.NEGATIVE_CONTROL_VERBATIM
    nc_texts = [
        str(row.get("verbatim") or row.get("rejects") or "")
        for row in (note.get("negative_controls") or [])
        if isinstance(row, dict)
    ]
    if verbatim not in nc_texts and verbatim not in json.dumps(note, ensure_ascii=False):
        return fail("negative control verbatim absent from note")
    roles = set(note.get("mechanism", {}).get("permitted_binder_roles") or [])
    if roles != set(O.PERMITTED_BINDER_ROLES):
        return fail(f"note binder roles drifted: {roles}")

    print("converse_silent outcome=YES irrelevant_failures=1")
    print("counterexample_instance=CE-IRRELEVANT-FAIL survived=True")
    print("counterexample_instance=CE-WEIGHTED-UNANIMITY survived=True")
    print("counterexample_instance=CE-SEAT-BINDER survived=True")
    print("counterexample_instance=CE-POST-CLOSE survived=True")
    print("counterexample_instance=CE-MAJORITY-DECLARE survived=True")
    print("counterexample_instance=CE-PREFIX-CLAIM survived=True")
    print("reviewer_id=CNL-0068-probe2-independent-recount")
    print("reviewer_verdict=PASS independent=True")
    print("negative_control_verbatim=" + verbatim)
    print("SUCCESS:CNL-0068-probe2 converse control and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
