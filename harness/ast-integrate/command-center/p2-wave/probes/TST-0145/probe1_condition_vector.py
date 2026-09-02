#!/usr/bin/env python3
"""Probe 1 (signal a): live predicate condition vector for condition 5.

Recomputes C5 on four fixtures. Does not take the receipt's conclusion as
the measurement. PASS requires correct SATISFIED, missing and wrong-id
UNSATISFIED with TST-9999 named, and quoted mention UNSATISFIED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import condition5 as C  # noqa: E402

ART = REPO / "command-center/receipts/TST-0145.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0145-probe1 {msg}")
    return 1


def main() -> int:
    matrix = C.run_matrix()
    compact = {
        "assertions": matrix["assertions"],
        "ok": matrix["ok"],
        "probe": "probe1-condition-vector",
        "unit_id": C.UNIT,
        "vector": {
            case_id: {
                "bytes": row["bytes"],
                "judge_c05": row["judge_c05"],
                "live_basis": row["live"]["basis"],
                "live_outcome": row["live"]["outcome"],
                "names_TST9999": row["names_TST9999"],
                "mutant_outcome": row["substring_mutant"]["outcome"],
                "schema_valid": row["schema_valid"],
            }
            for case_id, row in matrix["rows"].items()
        },
    }
    print(json.dumps(compact, sort_keys=True))

    if not matrix["ok"]:
        return fail(f"matrix assertions {matrix['assertions']}")
    rows = matrix["rows"]
    if rows["correct"]["live"]["outcome"] != "SATISFIED":
        return fail("correct sentinel did not satisfy condition 5")
    if rows["missing"]["live"]["outcome"] != "UNSATISFIED":
        return fail("missing sentinel did not fire condition 5")
    if rows["wrong_id"]["live"]["outcome"] != "UNSATISFIED":
        return fail("wrong-id sentinel did not fire condition 5")
    if not rows["wrong_id"]["names_TST9999"]:
        return fail("wrong-id basis omitted TST-9999 / SUCCESS:TST-9999")
    if rows["quoted_mention"]["live"]["outcome"] == "SATISFIED":
        return fail("quoted mention satisfied live condition 5")
    if rows["quoted_mention"]["substring_mutant"]["outcome"] != "SATISFIED":
        return fail("substring mutant did not fire on quoted mention (control dead)")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0145" not in text:
            return fail("receipt sentinel absent")
        if doc.get("unit_id") != "TST-0145":
            return fail("receipt unit_id")
        tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or []) if isinstance(t, dict)}
        for tid in (
            "TST-0145-T1",
            "TST-0145-NC1",
            "TST-0145-MISSING",
            "TST-0145-WRONG-ID",
        ):
            if tests.get(tid) != "PASS":
                return fail(f"receipt test {tid}={tests.get(tid)}")

    print(
        "live C5: correct SATISFIED; missing+wrong-id UNSATISFIED; "
        "wrong-id names SUCCESS:TST-9999; quoted mention rejected; "
        "substring mutant fooled"
    )
    print("SUCCESS:TST-0145-probe1 condition vector both-states use-vs-mention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
