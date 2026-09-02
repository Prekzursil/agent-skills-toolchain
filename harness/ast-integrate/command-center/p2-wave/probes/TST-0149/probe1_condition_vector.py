#!/usr/bin/env python3
"""Probe 1: live predicate condition vector, both-states control.

Signal (a): unregistered fixture has C2/C4/C5 SATISFIED and C11 UNSATISFIED
when platform/lib/completion_predicate.py reads the manifest FILE; registering
the row on disk flips C11 to SATISFIED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0149.json"
UNIT = "TST-0149"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0149-probe1 {msg}")
    return 1


def c11_of(vector: list) -> dict:
    for row in vector:
        if row.get("n") == 11:
            return row
    return {}


def main() -> int:
    live = S.evaluate()
    print(
        json.dumps(
            {
                "probe": "probe1-condition-vector",
                "unit_id": UNIT,
                "reducer_id": live.get("reducer_id"),
                "pass": live["pass"],
                "both_states": live["both_states"],
                "preconditions_hold": live["preconditions_hold"],
                "isolated_c2_c4_c5_satisfied": live["isolated_c2_c4_c5_satisfied"],
                "unregistered_c11": live["unregistered"]["c11_disk"]["outcome"],
                "registered_c11": live["registered"]["c11_disk"]["outcome"],
                "unregistered_c2": live["unregistered"]["live"]["c2"]["outcome"],
                "unregistered_c4": live["unregistered"]["live"]["c4"]["outcome"],
                "unregistered_c5": live["unregistered"]["live"]["c5"]["outcome"],
                "unregistered_vector_c11": c11_of(
                    live["unregistered"]["condition_vector"]
                ),
                "registered_vector_c11": c11_of(
                    live["registered"]["condition_vector"]
                ),
                "shared_predicate_present": live["shared_predicate_present"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not live["shared_predicate_present"]:
        return fail("platform/lib/completion_predicate.py absent")
    if not live["preconditions_hold"]:
        return fail("fixture artifact missing/unparseable/sentinel-absent")
    if not live["isolated_c2_c4_c5_satisfied"]:
        return fail("C2/C4/C5 did not stay SATISFIED on the unregistered fixture")
    if live["unregistered"]["c11_disk"]["outcome"] != "UNSATISFIED":
        return fail("unregistered fixture did not fail condition 11 from disk")
    if live["registered"]["c11_disk"]["outcome"] != "SATISFIED":
        return fail("registering on disk did not flip condition 11 to SATISFIED")
    if not live["both_states"]:
        return fail("both-states control failed")
    if not live["pass"]:
        return fail("scenario evaluate() pass=false")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return fail("catalog artifact unparseable")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:TST-0149" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    tests = doc.get("tests") if isinstance(doc.get("tests"), list) else []
    t1 = any(
        isinstance(t, dict) and t.get("id") == "TST-0149-T1" and t.get("result") == "PASS"
        for t in tests
    )
    if doc.get("both_states") is not True and ext.get("both_states") is not True and not t1:
        return fail("artifact missing both-states PASS")
    print("SUCCESS:TST-0149-probe1 condition-vector both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
