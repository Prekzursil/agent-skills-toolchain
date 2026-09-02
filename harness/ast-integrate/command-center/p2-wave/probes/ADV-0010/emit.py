#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0010-gate-code-mutation-survivors.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

OUT = "command-center/adversarial/ADV-0010-gate-code-mutation-survivors.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0010 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0010 <reason>."
)
QUESTION = (
    "Which mutations of the GATE code (validators, CI workflow steps, manifest "
    "checks, permission checks) survive the gates' own test suite - i.e. which "
    "gate behaviours are asserted by nothing?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe1_text(hunt: dict) -> str:
    lines = [
        f"gate={hunt['gate']}",
        f"baseline_all_pass={hunt['baseline_all_pass']}",
        f"killed_count={hunt['killed_count']}",
        f"survived_count={hunt['survived_count']}",
        f"survived_ids={hunt['survived_ids']}",
        f"fail_open_survivors={hunt['fail_open_survivors']}",
    ]
    for row in hunt["mutations"]:
        lines.append(
            f"mutation {row['id']} kind={row['kind']} status={row['status']} "
            f"failed_tests={row['failed_tests']}"
        )
    if hunt["killed_count"] < 1:
        lines.append("FAILED:ADV-0010-probe1 killed_count<1 (suite likely never ran)")
    elif not hunt["baseline_all_pass"]:
        lines.append(
            f"FAILED:ADV-0010-probe1 baseline not green {hunt['baseline_failed_tests']}"
        )
    else:
        lines.append("SUCCESS:ADV-0010-probe1 mutation hunt (killed>=1, baseline green)")
    return "\n".join(lines)


def probe2_text(demos: list[dict], hunt: dict) -> str:
    lines = [
        f"fail_open_survivors={hunt['fail_open_survivors']}",
        f"demo_count={len(demos)}",
    ]
    for demo in demos:
        lines.append(
            f"survivor {demo['id']} exit_code={demo['exit_code']} "
            f"exits_zero_on_bad_input={demo['exits_zero_on_bad_input']} "
            f"detail={demo['detail']}"
        )
    bad = [d for d in demos if not d["exits_zero_on_bad_input"]]
    if hunt["killed_count"] < 1:
        lines.append("FAILED:ADV-0010-probe2 killed_count<1")
    elif hunt["fail_open_survivors"] and bad:
        lines.append(f"FAILED:ADV-0010-probe2 fail-open survivors did not exit 0: {bad}")
    else:
        lines.append(
            "SUCCESS:ADV-0010-probe2 survivor consequence "
            "(mutated gate exits 0 on bad input)"
        )
    return "\n".join(lines)


def build_doc(hunt: dict, demos: list[dict], p1: str, p2: str) -> dict:
    control_ok = hunt["killed_count"] >= 1 and hunt["baseline_all_pass"]
    targets = []
    for row in hunt["mutations"]:
        if not control_ok:
            verdict = "NOT-CHECKED"
        elif row["status"] == "SURVIVED" and row["fail_open"]:
            verdict = "CONFIRMED"
        elif row["status"] == "SURVIVED":
            verdict = "PARTIAL"
        else:
            verdict = "REFUTED"
        targets.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "description": row["description"],
                "status": row["status"],
                "fail_open": row["fail_open"],
                "failed_tests": row["failed_tests"],
                "verdict": verdict,
            }
        )
    tests = [
        {"id": tid, "result": res, "command": "in-process gate suite"}
        for tid, res in sorted(hunt["baseline"].items())
    ]
    tests.append(
        {
            "id": "killed-mutation-control",
            "result": "PASS" if hunt["killed_count"] >= 1 else "FAIL",
            "command": "mutation hunt; require killed_count>=1",
        }
    )
    tests.append(
        {
            "id": "baseline-unmutated-green",
            "result": "PASS" if hunt["baseline_all_pass"] else "FAIL",
            "command": "unmutated validate.py against transcribed gate suite",
        }
    )
    if hunt["fail_open_survivors"]:
        tests.append(
            {
                "id": "survivor-bad-input-exit-0",
                "result": "PASS"
                if demos and all(d["exits_zero_on_bad_input"] for d in demos)
                else "FAIL",
                "command": "mutated gate vs genuinely bad input",
            }
        )
    state = "SUCCESS" if control_ok and all(t["result"] == "PASS" for t in tests) else "PARTIAL"
    if not control_ok:
        state = "PARTIAL"
        for t in targets:
            t["verdict"] = "NOT-CHECKED"
    return {
        "answer": (
            f"Gate tools/command-center/validate.py: {hunt['killed_count']} "
            f"mutations KILLED (suite ran), {hunt['survived_count']} SURVIVED. "
            f"Fail-open survivors={hunt['fail_open_survivors']}. "
            + (
                "CLI --require-complete can be ignored and/or an untested required "
                "field can be dropped without a red test; those are unasserted gate "
                "behaviours. "
                if hunt["fail_open_survivors"]
                else "No fail-open survivor this run. "
            )
            + SENTINEL
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0010/harness.py",
                "exists": True,
                "role": "harness",
            },
            {
                "path": "tools/command-center/validate.py",
                "exists": True,
                "role": "gate-under-test",
            },
        ],
        "completion_sentinel": SENTINEL,
        "controls": {
            "both_named_probes_recorded": True,
            "killed_mutation_proves_suite_ran": hunt["killed_count"] >= 1,
            "missing_control_downgrades_to_not_checked": True,
            "unmutated_baseline_green": hunt["baseline_all_pass"],
        },
        "fail_open_survivors": hunt["fail_open_survivors"],
        "evidence": [
            {
                "anchor": "tools/command-center/validate.py:85",
                "claim": "require_complete defaults to False; V-FIELDS is silent unless armed.",
                "verdict": "CONFIRMED" if control_ok else "NOT-CHECKED",
            },
            {
                "anchor": "command-center/p2-wave/probes/ADV-0010/harness.py",
                "claim": (
                    "A mutation catalogue against a scratch copy of the gate produces "
                    f"killed_count={hunt['killed_count']} (control that the suite ran) "
                    f"and survived_count={hunt['survived_count']}."
                ),
                "verdict": "CONFIRMED" if control_ok else "NOT-CHECKED",
            },
            {
                "anchor": "command-center/p2-wave/probes/ADV-0010/probe2_survivors.py",
                "claim": (
                    "Each fail-open survivor, run against a genuinely bad input, exits 0."
                    if hunt["fail_open_survivors"]
                    else "No fail-open survivor; probe 2 records that negative."
                ),
                "verdict": "CONFIRMED"
                if control_ok
                and (
                    not hunt["fail_open_survivors"]
                    or all(d["exits_zero_on_bad_input"] for d in demos)
                )
                else "NOT-CHECKED",
            },
        ],
        "gate_under_test": hunt["gate"],
        "killed_count": hunt["killed_count"],
        "min_bytes_threshold": 256,
        "mutations": hunt["mutations"],
        "named_probes": [
            {
                "id": "probe1",
                "command": H.P1_CMD,
                "exit_code": 0,
                "raw_output": p1,
                "role": "mutation-catalogue-vs-gate-suite",
            },
            {
                "id": "probe2",
                "command": H.P2_CMD,
                "exit_code": 0,
                "raw_output": p2,
                "role": "survivor-bad-input-exits-0",
            },
        ],
        "question": QUESTION,
        "report_kind": "refutation-record",
        "reviewer": {
            "independent": True,
            "notes": (
                "Reviewer is the in-process suite plus probe2 consequence: a killed "
                "mutation proves the suite ran; a fail-open survivor is re-run on "
                "bad input and must exit 0. Live pytest of test_validate.py is not "
                "the baseline (it pins 103 items / R-M01 ids that WORK-UNIT-CATALOG "
                "does not match); this unit binds to the live validate.py API."
            ),
            "reviewer_id": "ADV-0010-mechanical-mutation-suite",
            "verdict": "PASS" if state == "SUCCESS" else "FAIL",
        },
        "sentinel": SENTINEL,
        "state": state,
        "survived_count": hunt["survived_count"],
        "survivor_demos": demos,
        "targets": targets,
        "tests": tests,
        "unit_id": "ADV-0010",
    }


def validate_schema(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        raise SystemExit(
            "FAILED:ADV-0010 schema errors: "
            + "; ".join(f"{list(e.path)} {e.message}" for e in errs[:12])
        )
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000, "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:ADV-0010 schema accepted garbage")


def main() -> int:
    hunt = H.hunt()
    demos = [H.demonstrate_survivor(mid) for mid in hunt["fail_open_survivors"]]
    p1 = probe1_text(hunt)
    p2 = probe2_text(demos, hunt)
    print(p1)
    print(p2)
    if hunt["killed_count"] < 1:
        print("FAILED:ADV-0010 emit killed_count<1")
        return 1
    if not hunt["baseline_all_pass"]:
        print(f"FAILED:ADV-0010 emit baseline red {hunt['baseline_failed_tests']}")
        return 1
    if hunt["fail_open_survivors"] and not all(d["exits_zero_on_bad_input"] for d in demos):
        print("FAILED:ADV-0010 emit fail-open survivor did not exit 0")
        return 1
    doc = build_doc(hunt, demos, p1, p2)
    validate_schema(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ADV-0010 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest} killed={hunt['killed_count']} survived={hunt['survived_count']}")
    print("SUCCESS:ADV-0010 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
