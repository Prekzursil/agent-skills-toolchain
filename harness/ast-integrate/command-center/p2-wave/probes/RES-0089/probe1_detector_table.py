#!/usr/bin/env python3
"""Probe 1: detector table completeness + E3-without-baseline control.

Every row must carry a false-positive rate or the mark UNMEASURED. A
promoted mechanism must have effect size AND baseline. An E3 headline
must not promote. Partitioned reviewers must be disjoint.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import table as T  # noqa: E402

ART = REPO / "command-center/research/RES-0089.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0089-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if T.SENTINEL not in text:
        print("FAILED:RES-0089-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0089-probe1 self-declared {doc.get('state')}")
        return 1
    rows = doc.get("detector_table") or []
    ok, why = T.validate_table(rows)
    print(f"table_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0089-probe1 table validation")
        return 1

    # Both-states: the live table must stay green; an E3 headline-only
    # mutant that claims may_promote=true must go red.
    live_ok, live_why = T.validate_table(rows)
    mutant = copy.deepcopy(rows)
    mutant.append(T.e3_control_row())
    e3_ok, e3_why = T.validate_table(mutant)
    print(f"e3_control_unpromoted_ok={e3_ok} {e3_why}")
    if not e3_ok:
        print("FAILED:RES-0089-probe1 honest E3 control row was rejected")
        return 1
    bad = T.e3_control_row()
    bad["may_promote"] = True
    mutant_bad = copy.deepcopy(rows) + [bad]
    bad_ok, bad_why = T.validate_table(mutant_bad)
    print(f"e3_promoted_mutant_ok={bad_ok} {bad_why}")
    if bad_ok:
        print("FAILED:RES-0089-probe1 E3-promoted mutant was accepted")
        return 1
    if not live_ok:
        print(f"FAILED:RES-0089-probe1 live table {live_why}")
        return 1

    reviewers = ((doc.get("reviewer") or {}).get("reviewers")) or []
    if len(reviewers) < 2:
        print("FAILED:RES-0089-probe1 partitioned reviewers missing")
        return 1
    sets = []
    for r in reviewers:
        part = set(r.get("partition") or [])
        if not part:
            print("FAILED:RES-0089-probe1 empty partition")
            return 1
        sets.append(part)
    inter = sets[0].intersection(*sets[1:])
    print(f"partition_disjoint={not inter} overlap={sorted(inter)}")
    if inter:
        print("FAILED:RES-0089-probe1 reviewer partitions overlap")
        return 1
    if set(T.PARTITION_A) != sets[0] and set(T.PARTITION_A) != sets[1]:
        print("FAILED:RES-0089-probe1 partition A mismatch")
        return 1
    if set(T.PARTITION_B) != sets[0] and set(T.PARTITION_B) != sets[1]:
        print("FAILED:RES-0089-probe1 partition B mismatch")
        return 1

    applied = doc.get("applied_result") or {}
    if not applied:
        print("FAILED:RES-0089-probe1 applied_result missing")
        return 1
    print(
        "fpr_marks="
        + ",".join(sorted({str(r.get("false_positive_rate")) for r in rows}))
    )
    print("SUCCESS:RES-0089-probe1 detector table + E3 control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
