#!/usr/bin/env python3
"""Probe 1: missing-field rejection for each mandatory field; complete record admitted.

Also both-states: a complete record is admitted (silent on good), each
dropped field is refused (fires on bad). Empty/null values are not a
loophole. The ledger append path stores only admitted rows.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from bench.environment_record import (  # noqa: E402
    MANDATORY_FIELDS,
    InadmissibleResult,
    append_result,
    extract_environment,
    judge_environment,
    judge_result,
    make_complete_record,
)
from fixtures import admitted_result, rejected_missing, rejected_no_env  # noqa: E402

ART = REPO / "command-center/receipts/TST-0352.json"
SENTINEL = "SUCCESS:TST-0352"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0352-probe1 {msg}")
    return 1


def main() -> int:
    complete = admitted_result()
    v_ok = judge_result(complete)
    if not v_ok["admitted"]:
        return fail(f"complete record not admitted {v_ok}")

    tmp = Path(tempfile.mkdtemp(prefix="tst0352-ledger-"))
    written = append_result(tmp, complete)
    stored = written.read_text(encoding="utf-8").strip().splitlines()
    if len(stored) != 1:
        return fail(f"admitted append wrote {len(stored)} lines")

    per_field = []
    for field in MANDATORY_FIELDS:
        row = rejected_missing(field)
        verdict = judge_result(row)
        if verdict["admitted"]:
            return fail(f"missing {field} was admitted")
        if field not in verdict["missing_fields"]:
            return fail(f"missing {field} not listed {verdict}")
        try:
            append_result(tmp, row)
        except InadmissibleResult as exc:
            if field not in (exc.verdict.get("missing_fields") or []):
                return fail(f"append refused but wrong fields {exc.verdict}")
        else:
            return fail(f"append stored a result missing {field}")
        per_field.append({"field": field, "admitted": False, "refused_append": True})

    no_env = rejected_no_env()
    v_none = judge_result(no_env)
    if v_none["admitted"] or extract_environment(no_env) is not None:
        return fail(f"no-env row not refused {v_none}")
    if set(v_none["missing_fields"]) != set(MANDATORY_FIELDS):
        return fail(f"no-env missing_fields={v_none['missing_fields']}")

    # Empty / null values are invalid, not an undocumented pass.
    empty_cases = [
        ("os_build", {}),
        ("shell", {"name": ""}),
        ("interpreter_version", ""),
        ("package_versions", {}),
        ("git_core_autocrlf", "maybe"),
        ("locale", "   "),
        ("timezone", ""),
        ("concurrency", 0),
        ("commit_sha", "not-a-sha"),
        ("commit_sha", None),
    ]
    empty_rejected = []
    for field, bad in empty_cases:
        env = make_complete_record()
        env[field] = bad
        verdict = judge_environment(env)
        if verdict["admitted"]:
            return fail(f"invalid {field}={bad!r} admitted")
        empty_rejected.append(field)

    # Ledger still holds only the one admitted line.
    again = written.read_text(encoding="utf-8").strip().splitlines()
    if len(again) != 1:
        return fail(f"inadmissible rows leaked into ledger n={len(again)}")

    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            return fail("receipt sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
        admitted = doc.get("admitted_example") or {}
        rejected = doc.get("rejected_example") or {}
        if not judge_result(admitted)["admitted"]:
            return fail("receipt admitted_example is not admitted")
        if judge_result(rejected)["admitted"]:
            return fail("receipt rejected_example is admitted")

    out = {
        "probe": "probe1-missing-fields",
        "unit_id": "TST-0352",
        "pass": True,
        "complete_admitted": True,
        "fields_rejected": [p["field"] for p in per_field],
        "n_mandatory": len(MANDATORY_FIELDS),
        "no_env_rejected": True,
        "empty_or_invalid_rejected": empty_rejected,
        "ledger_admitted_lines": 1,
        "inadmissible_not_stored": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"admitted=1 rejected_fields={len(per_field)} "
        f"empty_rejected={len(empty_rejected)} ledger_lines=1"
    )
    print("SUCCESS:TST-0352-probe1 missing-field rejection and complete admit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
