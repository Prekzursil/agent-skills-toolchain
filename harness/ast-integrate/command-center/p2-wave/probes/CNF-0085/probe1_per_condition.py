#!/usr/bin/env python3
"""Probe 1: live per-condition differential of runner fan-in vs oracle.

Agreement is on verdict AND failing_condition_id. Aggregate boolean match is
not enough. The canonical exit-zero-with-missing-artifact row must be FAIL/C2
on both sides.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from artifact_view import comparison_table  # noqa: E402
from differential import (  # noqa: E402
    disagreements,
    distinct_fail_ids,
    expected_id_mismatches,
    runner_vs_oracle,
)

ART = REPO / "command-center/confirmation/CNF-0085-runner-predicate-differential.json"
SENTINEL = (
    "SUCCESS:CNF-0085 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the always-true stub "
    "control failed the differential and the per-condition comparison table "
    "is attached. Any other terminal state is FAILED:CNF-0085 <classification> "
    "with the diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0085-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0085-probe1 catalog sentinel absent from artifact")
        return 1
    if doc.get("unit_id") != "CNF-0085":
        print("FAILED:CNF-0085-probe1 unit_id", doc.get("unit_id"))
        return 1
    table = comparison_table(doc)
    if not isinstance(table, list) or len(table) < 12:
        print("FAILED:CNF-0085-probe1 comparison table missing or short")
        return 1

    live = runner_vs_oracle(REPO)
    diffs = disagreements(live)
    if diffs:
        print("FAILED:CNF-0085-probe1 runner/oracle disagree")
        print(json.dumps(diffs[:8], indent=2, default=str)[:4000])
        return 1
    expect_bad = expected_id_mismatches(live)
    if expect_bad:
        print("FAILED:CNF-0085-probe1 first-fail id not the planted condition")
        print(json.dumps(expect_bad[:8], indent=2, default=str)[:4000])
        return 1

    live_by_id = {r["row_id"]: r for r in live}
    canon = live_by_id.get("exit-zero-missing-artifact")
    if canon is None:
        print("FAILED:CNF-0085-probe1 canonical row missing")
        return 1
    if canon["candidate_verdict"] != "FAIL" or canon["oracle_verdict"] != "FAIL":
        print("FAILED:CNF-0085-probe1 exit-zero-missing-artifact not rejected")
        return 1
    if (
        canon["candidate_failing_condition_id"] != "C2"
        or canon["oracle_failing_condition_id"] != "C2"
    ):
        print("FAILED:CNF-0085-probe1 canonical failing id is not C2", canon)
        return 1

    pass_row = live_by_id.get("all-satisfied")
    if not pass_row or pass_row["candidate_verdict"] != "PASS":
        print("FAILED:CNF-0085-probe1 pass control did not PASS")
        return 1

    fail_ids = distinct_fail_ids(live)
    if len(fail_ids) < 12:
        print(
            f"FAILED:CNF-0085-probe1 only {len(fail_ids)} distinct failing ids "
            f"{fail_ids} — aggregate boolean could mask this"
        )
        return 1

    stored_ids = [r.get("row_id") for r in table]
    live_ids = [r["row_id"] for r in live]
    if stored_ids != live_ids:
        print("FAILED:CNF-0085-probe1 artifact table row_id order drifted")
        print("stored", stored_ids)
        print("live", live_ids)
        return 1
    for stored, now in zip(table, live):
        if stored.get("candidate_failing_condition_id") != now["candidate_failing_condition_id"]:
            print("FAILED:CNF-0085-probe1 stored vs live failing id drift", stored, now)
            return 1
        if stored.get("agree") is not True:
            print("FAILED:CNF-0085-probe1 stored row not agree", stored)
            return 1

    out = {
        "adjudicated": len(live),
        "disagreements": 0,
        "distinct_failing_condition_ids": fail_ids,
        "canonical_exit_zero_missing_artifact": "FAIL/C2",
        "pass_control": "PASS",
        "pass": True,
        "probe": "probe1-per-condition",
        "unit_id": "CNF-0085",
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"rows={len(live)} distinct_fail_ids={fail_ids} "
        "canonical=FAIL/C2 pass_control=PASS"
    )
    print("SUCCESS:CNF-0085-probe1 per-condition runner/oracle agreement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
