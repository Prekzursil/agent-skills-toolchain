#!/usr/bin/env python3
"""Probe 2: apply each published predicate to the estate EZMA observation.

Control: the twelve-condition reducer must return INCOMPLETE on EZMA.
POSIX/exit-0 must return COMPLETE (demonstrating the miss).
in-toto REQUIRE must return INCOMPLETE (demonstrating a CATCH).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from predicates import (  # noqa: E402
    EZMA,
    PREDICATES,
    estate_twelve,
    ezma_result,
    in_toto_require,
    posix_exit,
)

ART = REPO / "command-center/research/RES-0088.json"


def main() -> int:
    failed = []
    applied = []
    for p in PREDICATES:
        verdict = p.apply(EZMA)
        expected_ezma = ezma_result(p)
        got = "MISS" if verdict == "COMPLETE" else "CATCH"
        row = {
            "id": p.id,
            "verdict_on_ezma": verdict,
            "ezma": got,
            "missed_failure": p.missed_failure,
        }
        applied.append(row)
        if got != expected_ezma:
            failed.append(f"{p.id}: ezma {got} != {expected_ezma}")
        if not (p.missed_failure or "").strip():
            failed.append(f"{p.id}: unnamed missed failure")

    twelve = estate_twelve(EZMA)
    if twelve != "INCOMPLETE":
        failed.append(f"estate twelve-condition reducer returned {twelve} on EZMA")
    if posix_exit(EZMA) != "COMPLETE":
        failed.append("posix_exit did not MISS EZMA (expected COMPLETE)")
    if in_toto_require(EZMA) != "INCOMPLETE":
        failed.append("in_toto_require did not CATCH EZMA")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        control = doc.get("ezma_control") or {}
        if control.get("estate_twelve_verdict") != "INCOMPLETE":
            failed.append("artifact ezma_control.estate_twelve_verdict is not INCOMPLETE")
        art_rows = {r.get("predicate_id"): r for r in (doc.get("predicate_table") or [])}
        for row in applied:
            ar = art_rows.get(row["id"]) or {}
            if ar.get("ezma") != row["ezma"]:
                failed.append(f"artifact ezma drift {row['id']}: {ar.get('ezma')} != {row['ezma']}")

    misses = sum(1 for r in applied if r["ezma"] == "MISS")
    catches = sum(1 for r in applied if r["ezma"] == "CATCH")
    out = {
        "probe": "probe2-ezma-control",
        "unit_id": "RES-0088",
        "estate_twelve_on_ezma": twelve,
        "posix_on_ezma": posix_exit(EZMA),
        "in_toto_require_on_ezma": in_toto_require(EZMA),
        "misses": misses,
        "catches": catches,
        "applied": applied,
        "pass": not failed,
        "failures": failed,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if failed:
        print("FAILED:RES-0088-probe2")
        return 1
    print(
        "SUCCESS:RES-0088-probe2 EZMA control: "
        f"twelve=INCOMPLETE posix=MISS in-toto=CATCH misses={misses} catches={catches}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
