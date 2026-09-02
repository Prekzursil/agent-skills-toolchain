#!/usr/bin/env python3
"""Named probe 1: every fixture gets a field-level comparison, not a load boolean."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import state as S  # noqa: E402


def main() -> int:
    rows = S.evaluate_all()
    by_id = {r["id"]: r for r in rows}
    if len(rows) < 4:
        print("FAILED:CNF-0048-probe1 fewer than 4 fixtures")
        return 1
    for row in rows:
        comps = row["field_comparisons"]
        if not isinstance(comps, list) or len(comps) < 1:
            print(f"FAILED:CNF-0048-probe1 {row['id']} missing field_comparisons")
            return 1
        if all(set(c.keys()) <= {"loaded", "ok"} for c in comps):
            print(f"FAILED:CNF-0048-probe1 {row['id']} comparisons are load booleans")
            return 1
        needed = ("path", "intended", "loaded", "equal", "meaning_changed")
        for c in comps:
            if any(k not in c for k in needed):
                print(f"FAILED:CNF-0048-probe1 {row['id']} comparison missing keys")
                return 1
        print(
            f"fixture {row['id']} loaded={row['old_version_load']['loaded']} "
            f"refused={row['old_version_load']['refused']} "
            f"compared={row['compared_count']} equal={row['equal_count']} "
            f"meaning_changed={row['meaning_changed_count']} outcome={row['outcome']}"
        )

    migrated = by_id["reverse-migrated"]
    if not migrated["old_version_load"]["loaded"]:
        print("FAILED:CNF-0048-probe1 reverse-migrated did not load in old v1")
        print(migrated["old_version_load"]["message"])
        return 1
    if migrated["meaning_changed_count"] != 0:
        changed = [c for c in migrated["field_comparisons"] if c["meaning_changed"]]
        print("FAILED:CNF-0048-probe1 reverse-migrated still has meaning changes")
        print(json.dumps(changed[:8], indent=2, default=str))
        return 1
    if migrated["compared_count"] < 8:
        print("FAILED:CNF-0048-probe1 reverse-migrated compared too few fields")
        return 1

    summary = {
        "adjudicated": len(rows),
        "fixtures": [
            {
                "id": r["id"],
                "outcome": r["outcome"],
                "compared": r["compared_count"],
                "meaning_changed": r["meaning_changed_count"],
            }
            for r in rows
        ],
        "pass": True,
        "probe": "probe1-field-compare",
        "unit_id": "CNF-0048",
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0048-probe1 field-level comparison on every fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
