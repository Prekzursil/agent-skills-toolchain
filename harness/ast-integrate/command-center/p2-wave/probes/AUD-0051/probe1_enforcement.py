#!/usr/bin/env python3
"""Probe 1: run declared coverage-enforcement commands and capture reports.

Also runs the catalog control: pytest WITHOUT --coverage/--cov on one project
and requires the extractor to report NOT-CHECKED rather than a number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
from coverage_extract import canned_control, extract_coverage  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

UNIT = "AUD-0051"
ART = C.REPO / C.OUT_REL
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def schema_discriminates() -> dict:
    schema_path = C.REPO / C.SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    garbage = list(validator.iter_errors({"totally": "unrelated", "n": 999999}))
    empty = list(validator.iter_errors({}))
    return {
        "schema_exists": schema_path.is_file(),
        "garbage_rejected": len(garbage) > 0,
        "empty_rejected": len(empty) > 0,
        "garbage_error_count": len(garbage),
        "empty_error_count": len(empty),
    }


def main() -> int:
    canned = canned_control()
    plain = C.run_plain_pytest_without_coverage()
    inop = C.run_inoperable_fixture()
    live = C.discover_live()
    runs = C.run_live_enforcement(live)
    ci = C.read_ci_coverage_job()
    schema = schema_discriminates()
    tooling = C.coverage_tooling()

    live_numeric = [
        p for p in live if str(p.get("coverage") or "").endswith("%")
    ]
    ungated = [p for p in live if not p.get("has_thresholds_file")]
    ungated_folded = [
        p["path"]
        for p in ungated
        if p.get("coverage") not in (None, "NOT-CHECKED")
        and str(p.get("coverage")) != "NOT-CHECKED"
    ]

    control_ok = (
        canned["pass"]
        and plain["coverage"] == "NOT-CHECKED"
        and plain["exit_code"] == 0
        and inop["coverage"] == "NOT-CHECKED"
        and inop["exit_code"] != 0
        and extract_coverage("27 passed (27)")[0] == "NOT-CHECKED"
    )
    ok = (
        control_ok
        and schema["schema_exists"]
        and schema["garbage_rejected"]
        and schema["empty_rejected"]
        and not ungated_folded
        and ci["present"]
        and ci["declares_pytest_without_cov"]
        and not ci["command_has_coverage_instrumentation"]
    )
    payload = {
        "pass": bool(ok),
        "probe": "probe1-enforcement",
        "unit_id": UNIT,
        "canned_control": {
            "pass": canned["pass"],
            "bad": canned["bad_state_result"],
            "good": canned["good_state_result"],
        },
        "plain_pytest_without_cov": {
            "exit_code": plain["exit_code"],
            "coverage": plain["coverage"],
            "provenance": plain["coverage_provenance"],
            "output_tail": plain["output_tail"][-400:],
        },
        "inoperable_fixture": {
            "exit_code": inop["exit_code"],
            "coverage": inop["coverage"],
            "provenance": inop["coverage_provenance"],
        },
        "live_projects": len(live),
        "live_gated": sum(1 for p in live if p.get("has_thresholds_file")),
        "live_enforcement_runs": len(runs),
        "live_numeric_coverage_count": len(live_numeric),
        "ungated_folded_into_number": ungated_folded,
        "ci": {
            "path": ci["path"],
            "present": ci["present"],
            "job_name_contains_coverage": ci["job_name_contains_coverage"],
            "command_has_coverage_instrumentation": ci[
                "command_has_coverage_instrumentation"
            ],
            "declares_pytest_without_cov": ci.get("declares_pytest_without_cov"),
        },
        "coverage_tooling": tooling,
        "schema": schema,
    }
    print(json.dumps(payload, sort_keys=True, default=str))

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail(f"artifact absent {ART}")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    headline = doc.get("headline") or {}
    if headline.get("projects") != len(live):
        return fail(f"headline projects {headline.get('projects')} != {len(live)}")
    if headline.get("gated") != sum(1 for p in live if p.get("has_thresholds_file")):
        return fail(f"headline gated {headline.get('gated')}")
    if not live_numeric:
        if headline.get("repo_line_coverage") != "NOT-CHECKED":
            return fail("repo_line_coverage is not NOT-CHECKED")
        if headline.get("repo_branch_coverage") != "NOT-CHECKED":
            return fail("repo_branch_coverage is not NOT-CHECKED")
    named = doc.get("named_probes") or []
    if len(named) < 2:
        return fail("named probes missing from artifact")
    if not ok:
        return fail("enforcement/control checks failed")
    print(
        "SUCCESS:AUD-0051-probe1 enforcement commands recorded; "
        "pytest-without-coverage is NOT-CHECKED; inoperable gate does not "
        "mint a coverage number"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
