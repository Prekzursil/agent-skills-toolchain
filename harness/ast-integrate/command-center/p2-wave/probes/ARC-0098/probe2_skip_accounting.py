#!/usr/bin/env python3
"""Named probe 2: skip accounting. A report with skips is not an unqualified PASS.

Mechanically different from probe 1: does not re-score PASS/FAIL/ERROR
distinction. Re-runs skip-mix vs all-pass and checks live verdict lines.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import runner as R  # noqa: E402
import schema_local as S  # noqa: E402

UNIT = "ARC-0098"
ART = REPO / "command-center" / "phase4" / "conformance" / "ARC-0098.json"
UNQUALIFIED = "CONFORMANCE-VERDICT: PASS"
QUALIFIED = "CONFORMANCE-VERDICT: PASS-WITH-SKIPS"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:ARC-0098" not in json.dumps(doc):
        return fail("sentinel absent")

    skip_mix = R.run_report(R.DEFAULT_SUITES, select=["known-pass", "known-skip"])
    all_pass = R.run_report(R.DEFAULT_SUITES, select=["known-pass"])
    discover = R.run_report(
        R.DEFAULT_SUITES, select=["known-pass"], discover_contracts=True
    )

    skipped = [r for r in skip_mix["suites"] if r["verdict"] == "SKIPPED"]
    if skip_mix["counts"]["skipped"] != len(skipped) or not skipped:
        return fail("skip count mismatch", skip_mix["counts"])
    if skip_mix["skipped_ids"] != [r["id"] for r in skipped]:
        return fail("skipped ids not itemized", skip_mix.get("skipped_ids"))
    if skip_mix["overall_verdict"] != "PASS-WITH-SKIPS":
        return fail("skip mix overall", skip_mix["overall_verdict"])
    if skip_mix["unqualified_pass"] is not False:
        return fail("skip mix unqualified_pass true")
    if skip_mix["verdict_line"] == UNQUALIFIED:
        return fail("skip mix printed unqualified PASS", skip_mix["verdict_line"])
    if skip_mix["verdict_line"] != QUALIFIED:
        return fail("skip mix verdict line", skip_mix["verdict_line"])
    if skip_mix["exit_code"] != 3:
        return fail("skip mix exit", skip_mix["exit_code"])

    if all_pass["overall_verdict"] != "PASS" or all_pass["unqualified_pass"] is not True:
        return fail("all-pass control", all_pass)
    if all_pass["verdict_line"] != UNQUALIFIED:
        return fail("all-pass must print unqualified PASS", all_pass["verdict_line"])
    if all_pass["exit_code"] != 0:
        return fail("all-pass exit", all_pass["exit_code"])
    if all_pass["counts"]["skipped"] != 0:
        return fail("all-pass had skips", all_pass["counts"])

    runs = S.control_runs_of(doc)
    rec_skip = runs.get("skip_mix") or {}
    if rec_skip.get("overall_verdict") != skip_mix["overall_verdict"]:
        return fail("artifact skip_mix drift", rec_skip)
    if rec_skip.get("skipped_ids") != skip_mix["skipped_ids"]:
        return fail("artifact skipped_ids drift", rec_skip.get("skipped_ids"))
    rec_pass = runs.get("all_pass") or {}
    if rec_pass.get("verdict_line") != all_pass["verdict_line"]:
        return fail("artifact all_pass drift", rec_pass)

    absent = [
        r
        for r in discover["suites"]
        if str(r.get("skip_reason") or "") == "artifact-absent"
    ]
    if len(absent) < 3:
        return fail(
            "upstream contracts not skipped as artifact-absent",
            discover["suites"],
        )
    if discover["unqualified_pass"] is not False:
        return fail("discover run manufactured unqualified PASS")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("reviewer", reviewer)

    payload = {
        "pass": True,
        "probe": "probe2-skip-accounting",
        "unit_id": UNIT,
        "skip_mix_verdict": skip_mix["overall_verdict"],
        "skip_mix_line": skip_mix["verdict_line"],
        "skipped_ids": skip_mix["skipped_ids"],
        "skipped_count": skip_mix["counts"]["skipped"],
        "all_pass_line": all_pass["verdict_line"],
        "upstream_absent_skipped": len(absent),
        "unqualified_pass_forbidden_when_skips": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"skip_mix={skip_mix['overall_verdict']} skipped={skip_mix['skipped_ids']} "
        f"all_pass_line={all_pass['verdict_line']}"
    )
    print("SUCCESS:ARC-0098-probe2 skip-accounting no-unqualified-PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
