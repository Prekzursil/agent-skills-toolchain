#!/usr/bin/env python3
"""Probe 2: independent recount of independent sources from stored lineage.

Does not call mapper.score. Re-collapses identity keys on each conclusion's
recorded lineage_records and checks the artifact counts. Defaults to REFUTED
on mismatch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lineage import collapse_independent  # noqa: E402

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0185-evidence-map-coverage-holes.json"
)
SENTINEL = "SUCCESS:RES-0185"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0185-probe2 {msg}")
    return 1


def recount(lineage_records: list) -> int:
    if not isinstance(lineage_records, list):
        return 0
    locs = [x for x in lineage_records if isinstance(x, dict)]
    return len(collapse_independent(locs))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")

    rows = [c for c in (doc.get("conclusions") or []) if isinstance(c, dict)]
    if len(rows) < 4:
        return fail(f"too few conclusions n={len(rows)}")

    mismatches = []
    program_single = 0
    program_n = 0
    for row in rows:
        live_n = recount(row.get("lineage_records") or [])
        stored = int(row.get("independent_source_count") or 0)
        if live_n != stored:
            mismatches.append(
                {"id": row.get("id"), "live": live_n, "stored": stored}
            )
        live_single = live_n == 1
        stored_single = bool(row.get("single_source"))
        if live_single != stored_single:
            mismatches.append(
                {
                    "id": row.get("id"),
                    "live_single": live_single,
                    "stored_single": stored_single,
                }
            )
        if live_n == 0 and row.get("support_status") != "UNSUPPORTED":
            mismatches.append(
                {"id": row.get("id"), "empty_not_unsupported": True}
            )
        if not row.get("plant"):
            program_n += 1
            if live_single:
                program_single += 1

    stored_headline = int(doc.get("single_source_count") or -1)
    stored_prog = int(doc.get("program_conclusion_count") or -1)
    payload = {
        "probe": "probe2-independent-recount",
        "program_n_live": program_n,
        "single_source_live": program_single,
        "single_source_stored": stored_headline,
        "mismatch_n": len(mismatches),
        "verdict": "REFUTED" if mismatches or stored_headline != program_single else "PASS",
    }
    print(json.dumps(payload, sort_keys=True))
    if mismatches:
        print(json.dumps(mismatches[:8], indent=2)[:4000])
        return fail("lineage recount mismatch; reviewer defaults to REFUTED")
    if stored_headline != program_single:
        return fail(
            f"headline single_source_count={stored_headline} live={program_single}"
        )
    if stored_prog != program_n:
        return fail(f"program_conclusion_count={stored_prog} live={program_n}")
    print(
        f"INDEPENDENT RECOUNT: program_n={program_n} single-source={program_single} "
        "matches artifact; empty lineage remains UNSUPPORTED."
    )
    print("SUCCESS:RES-0185-probe2 independent lineage recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
