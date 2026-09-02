#!/usr/bin/env python3
"""Live condition-5 harness for TST-0145.

Builds four schema-valid non-empty fixtures and evaluates the shared
completion-predicate C5 (role-based) plus the substring mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from completion_predicate import (  # noqa: E402
    evaluate_c05_artifact,
    judge,
    substring_c05_artifact,
)

UNIT = "TST-0145"
EXPECTED = f"SUCCESS:{UNIT}"
FOREIGN = "TST-9999"
FOREIGN_SENTINEL = f"SUCCESS:{FOREIGN}"
CASES = ("correct", "missing", "wrong_id", "quoted_mention")
FIXTURE_SCHEMA_REL = "command-center/p2-wave/probes/TST-0145/fixture.schema.json"
RUNTIME = HERE / "runtime"
QUESTION = (
    "Does condition 5 fire for a schema-valid, non-empty artifact whose "
    "completion sentinel is missing or belongs to a different unit id?"
)


def _load_fixture_schema() -> dict[str, Any]:
    return json.loads((REPO / FIXTURE_SCHEMA_REL).read_text(encoding="utf-8"))


def schema_errors(doc: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    import jsonschema

    schema = schema if schema is not None else _load_fixture_schema()
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{list(err.path)}: {err.message}"
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def _base(case_id: str, *, answer: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "answer": answer,
        "artifacts": [
            {
                "exists": True,
                "path": f"command-center/p2-wave/probes/TST-0145/runtime/{case_id}/artifact.json",
                "role": "primary",
            }
        ],
        "case_id": case_id,
        "question": QUESTION,
        "state": "SUCCESS",
        "unit_id": UNIT,
    }
    if extra:
        doc.update(extra)
    return doc


def fixture_docs() -> dict[str, dict[str, Any]]:
    return {
        "correct": _base(
            "correct",
            answer=(
                "This fixture carries the completion sentinel in the sentinel "
                "role field so condition 5 must SATISFY."
            ),
            extra={
                "completion_sentinel": EXPECTED,
                "sentinel": EXPECTED,
            },
        ),
        "missing": _base(
            "missing",
            answer=(
                "This fixture is schema-valid and non-empty but has no completion "
                "token of any unit, so condition 5 must fire as UNSATISFIED."
            ),
        ),
        "wrong_id": _base(
            "wrong_id",
            answer=(
                "This fixture completed a different unit. Its sentinel role names "
                "that other unit, so condition 5 must fail and name the mismatch."
            ),
            extra={
                "completion_sentinel": FOREIGN_SENTINEL,
                "sentinel": FOREIGN_SENTINEL,
            },
        ),
        "quoted_mention": _base(
            "quoted_mention",
            answer=(
                "Quoted example only: 'the receipt must contain "
                f"{EXPECTED} on a terminal line' is a mention, not a live "
                "sentinel role, so condition 5 must NOT satisfy."
            ),
        ),
    }


def write_fixtures() -> dict[str, dict[str, Any]]:
    schema = _load_fixture_schema()
    docs = fixture_docs()
    written: dict[str, dict[str, Any]] = {}
    for case_id, doc in docs.items():
        errs = schema_errors(doc, schema)
        if errs:
            raise RuntimeError(f"fixture {case_id} schema-invalid: {errs[:4]}")
        case_dir = RUNTIME / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / "artifact.json"
        text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        raw = path.read_bytes()
        if len(raw) <= 0:
            raise RuntimeError(f"fixture {case_id} empty")
        written[case_id] = {
            "path": path,
            "rel": (
                "command-center/p2-wave/probes/TST-0145/runtime/"
                f"{case_id}/artifact.json"
            ),
            "text": text,
            "bytes": len(raw.replace(b"\r\n", b"\n")),
            "doc": doc,
            "schema_valid": True,
        }
    return written


def evaluate_case(case_id: str, text: str) -> dict[str, Any]:
    live = evaluate_c05_artifact(text, UNIT)
    mutant = substring_c05_artifact(text, UNIT)
    record = {
        "artifact_bytes": len(text.encode("utf-8")),
        "artifact_exists": True,
        "artifact_json_ok": True,
        "artifact_text": text,
        "consumer_read": True,
        "evidence_anchor_count": 2,
        "expected_sentinel": EXPECTED,
        "manifest_registered": True,
        "negative_control_fired": True,
        "open_p0_p1": False,
        "reviewer_verdict": "PASS",
        "sentinel_present": True,
        "state": "SUCCESS",
        "tests_passed": True,
        "tests_ran": True,
        "unit_id": UNIT,
    }
    judged = judge(record)
    return {
        "case_id": case_id,
        "live": live,
        "substring_mutant": mutant,
        "judge_c05": judged["conditions"].get("C05"),
        "judge_complete": judged["complete"],
    }


def names_foreign(basis: str, detail: dict[str, Any] | None) -> bool:
    blob = basis + " " + json.dumps(detail or {}, sort_keys=True)
    return FOREIGN in blob and FOREIGN_SENTINEL in blob


def run_matrix() -> dict[str, Any]:
    fixtures = write_fixtures()
    rows: dict[str, Any] = {}
    for case_id in CASES:
        fx = fixtures[case_id]
        row = evaluate_case(case_id, fx["text"])
        live = row["live"]
        row["schema_valid"] = fx["schema_valid"]
        row["bytes"] = fx["bytes"]
        row["rel"] = fx["rel"]
        row["names_TST9999"] = names_foreign(str(live.get("basis") or ""), live.get("detail"))
        rows[case_id] = row

    correct = rows["correct"]
    missing = rows["missing"]
    wrong = rows["wrong_id"]
    quoted = rows["quoted_mention"]

    both_states = (
        correct["live"]["outcome"] == "SATISFIED"
        and missing["live"]["outcome"] == "UNSATISFIED"
        and wrong["live"]["outcome"] == "UNSATISFIED"
    )
    wrong_names = bool(wrong["names_TST9999"])
    use_vs_mention = quoted["live"]["outcome"] == "UNSATISFIED"
    mutant_fooled = quoted["substring_mutant"]["outcome"] == "SATISFIED"
    mutant_silent_on_good = correct["substring_mutant"]["outcome"] == "SATISFIED"
    judge_tracks_live = all(
        (rows[c]["judge_c05"] == "PASS") is (rows[c]["live"]["outcome"] == "SATISFIED")
        for c in CASES
    )
    all_schema = all(rows[c]["schema_valid"] and rows[c]["bytes"] > 0 for c in CASES)

    ok = (
        both_states
        and wrong_names
        and use_vs_mention
        and mutant_fooled
        and mutant_silent_on_good
        and judge_tracks_live
        and all_schema
    )
    return {
        "ok": ok,
        "unit_id": UNIT,
        "expected_sentinel": EXPECTED,
        "rows": rows,
        "assertions": {
            "both_states_correct_passes_missing_and_wrong_fail": both_states,
            "wrong_id_names_TST9999": wrong_names,
            "quoted_mention_does_not_satisfy_live_c5": use_vs_mention,
            "substring_mutant_satisfies_quoted_mention": mutant_fooled,
            "substring_mutant_silent_on_correct": mutant_silent_on_good,
            "judge_c05_tracks_live_evaluator": judge_tracks_live,
            "all_fixtures_schema_valid_nonempty": all_schema,
        },
    }


def grep_signals(text: str) -> dict[str, Any]:
    """Independent byte scan: token presence, not the C5 evaluator."""
    own = EXPECTED in text
    foreign = FOREIGN_SENTINEL in text
    own_in_role = False
    foreign_in_role = False
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        doc = None
    if isinstance(doc, dict):
        for key in ("sentinel", "completion_sentinel"):
            val = doc.get(key)
            if val == EXPECTED:
                own_in_role = True
            if val == FOREIGN_SENTINEL:
                foreign_in_role = True
    return {
        "own_token_in_bytes": own,
        "foreign_token_in_bytes": foreign,
        "own_in_role": own_in_role,
        "foreign_in_role": foreign_in_role,
    }


if __name__ == "__main__":
    matrix = run_matrix()
    print(json.dumps({k: matrix[k] for k in ("ok", "assertions")}, indent=2, sort_keys=True))
    raise SystemExit(0 if matrix["ok"] else 1)
