#!/usr/bin/env python3
"""Probe 1: every published predicate row names a concrete missed failure.

Fails if a row has an empty missed-failure, if either evidence rail is missing,
unquoted, or non-200, or if EZMA CATCH/MISS is inconsistent with the named hole.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from predicates import PREDICATES, ezma_result  # noqa: E402
from rails import rail_record  # noqa: E402

ART = REPO / "command-center/research/RES-0088.json"


def main() -> int:
    rows = []
    failed = []
    for p in PREDICATES:
        r1 = rail_record(p.rails[0], p.quotes[0], p.permalinks[0])
        r2 = rail_record(p.rails[1], p.quotes[1], p.permalinks[1])
        ezma = ezma_result(p)
        miss = (p.missed_failure or "").strip()
        rec = {
            "id": p.id,
            "missed_failure": miss,
            "ezma": ezma,
            "rail1_ok": r1["http_ok"] and r1["quote_found"],
            "rail2_ok": r2["http_ok"] and r2["quote_found"],
            "rail1": {k: r1[k] for k in ("snapshot", "http_status", "sha256", "quote_found")},
            "rail2": {k: r2[k] for k in ("snapshot", "http_status", "sha256", "quote_found")},
        }
        rows.append(rec)
        if not miss:
            failed.append(f"{p.id}: empty missed_failure")
        if ezma == "MISS" and miss != "exit-zero-missing-artifact":
            failed.append(f"{p.id}: EZMA MISS must name exit-zero-missing-artifact, got {miss!r}")
        if ezma == "CATCH" and miss == "exit-zero-missing-artifact":
            failed.append(f"{p.id}: EZMA CATCH cannot claim EZMA as the missed failure")
        if not rec["rail1_ok"]:
            failed.append(f"{p.id}: rail1 failed {r1}")
        if not rec["rail2_ok"]:
            failed.append(f"{p.id}: rail2 failed {r2}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        table = doc.get("predicate_table") or []
        if len(table) != len(PREDICATES):
            failed.append(f"artifact predicate_table len {len(table)} != {len(PREDICATES)}")
        for src, dst in zip(PREDICATES, table):
            named = (dst.get("missed_failure") or "").strip()
            if named != src.missed_failure:
                failed.append(f"artifact row {src.id} missed_failure drift {named!r}")
            if not named:
                failed.append(f"artifact row {src.id} empty missed_failure")

    out = {
        "probe": "probe1-named-missed-failures",
        "unit_id": "RES-0088",
        "rows": len(rows),
        "all_named": all(r["missed_failure"] for r in rows),
        "two_rails_each": all(r["rail1_ok"] and r["rail2_ok"] for r in rows),
        "pass": not failed,
        "failures": failed,
        "table": rows,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if failed:
        print("FAILED:RES-0088-probe1")
        return 1
    print("SUCCESS:RES-0088-probe1 named missed failure per published predicate, two rails each")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
