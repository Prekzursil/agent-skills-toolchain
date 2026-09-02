#!/usr/bin/env python3
"""Probe 2: independent recount / re-tabulation (does not trust the note's prose)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import composition as C  # noqa: E402

NOTE = C.REPO / "command-center/design/council/CNL-0046-executable-runtime-semantics-for-the-7-meta-composition-pr.md"


def main() -> int:
    catalog = C.catalog_named_members()
    catalog_ids = [pid for pid, _ in catalog]
    fixture_ids = [r["id"] for r in C.family_records()]
    recomputed_pairs = C.all_meta_pairs()
    conflict_n = sum(1 for p in recomputed_pairs if p["conflict"])
    print(f"recount_catalog_n={len(catalog_ids)} ids={catalog_ids}")
    print(f"recount_fixture_n={len(fixture_ids)} ids={fixture_ids}")
    print(f"recomputed_pairs={len(recomputed_pairs)} conflicts={conflict_n}")

    if catalog_ids != fixture_ids:
        print("FAILED:CNL-0046-probe2 catalog vs fixture id disagreement")
        return 1
    if len(catalog_ids) != C.EXPECTED_N:
        print("FAILED:CNL-0046-probe2 count is not 7")
        return 1
    if len(recomputed_pairs) != 21:
        print(f"FAILED:CNL-0046-probe2 pair table size {len(recomputed_pairs)}")
        return 1

    if not NOTE.is_file():
        print("FAILED:CNL-0046-probe2 design note missing")
        return 1
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    note_ids = [r.get("id") for r in (note.get("records") or [])]
    print(f"note_ids={note_ids}")
    if note_ids != catalog_ids:
        print("FAILED:CNL-0046-probe2 note ids disagree with catalog recount")
        return 1

    note_pairs = note.get("conflict_pairs") or []
    if len(note_pairs) != 21:
        print(f"FAILED:CNL-0046-probe2 note pair count {len(note_pairs)}")
        return 1
    note_conflicts = {
        (p["a"], p["b"]): (bool(p.get("conflict")), tuple(p.get("axes") or []))
        for p in note_pairs
    }
    for row in recomputed_pairs:
        key = (row["a"], row["b"])
        got = note_conflicts.get(key)
        expected = (row["conflict"], tuple(row["axes"]))
        print(f"pair {key[0]}x{key[1]} note={got} recomputed={expected}")
        if got != expected:
            print("FAILED:CNL-0046-probe2 conflict table disagreement")
            return 1

    reviewer = note.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        print("FAILED:CNL-0046-probe2 reviewer not independent")
        return 1
    if int(reviewer.get("recount_n") or 0) != C.EXPECTED_N:
        print("FAILED:CNL-0046-probe2 reviewer recount_n")
        return 1
    if "SUCCESS:CNL-0046" not in NOTE.read_text(encoding="utf-8"):
        print("FAILED:CNL-0046-probe2 sentinel absent")
        return 1
    print("SUCCESS:CNL-0046-probe2 independent recount re-tabulation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
