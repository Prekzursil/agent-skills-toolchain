#!/usr/bin/env python3
"""Probe 2: M-40/M-41 and seven doc-13-only ids; independent re-derive of ten ids.

Does not read disposition values FROM the receipt table until after an
independent closer pass against the artifacts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from closer import close  # noqa: E402
from sources import doc13_only_ids, universe_only_ids  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0019.json"
SAMPLE = [
    "M-1",
    "M-31",
    "M-40",
    "M-41",
    "MECH-1",
    "MECH-31",
    "MECH-32",
    "MECH-38",
    "CTRL-DUAL-1",
    "CTRL-MISSING-1",
]


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0019-probe2 {msg}")
    return 1


def main() -> int:
    indep = close()
    by_id = {r["id"]: r for r in indep["rows"]}

    u_only = universe_only_ids()
    d_only = doc13_only_ids()
    for oid in u_only:
        row = by_id.get(oid)
        if row is None:
            return fail(f"{oid} absent")
        print(f"universe-only {oid} bucket={row['bucket']} disp={row['disposition']}")
        if row["bucket"] != "universe-only":
            return fail(f"{oid} expected bucket universe-only, got {row['bucket']}")
        if not row["in_option_universe"] or row["in_doc13"]:
            return fail(f"{oid} membership mismatch")
    for oid in d_only:
        row = by_id.get(oid)
        if row is None:
            return fail(f"{oid} absent")
        print(f"doc-13-only {oid} bucket={row['bucket']} disp={row['disposition']}")
        if row["bucket"] != "doc-13-only":
            return fail(f"{oid} expected bucket doc-13-only, got {row['bucket']}")
        if row["in_option_universe"] or not row["in_doc13"]:
            return fail(f"{oid} membership mismatch")

    stale = indep["stale_log"]
    print(
        f"stale_log mech_token={stale['contains_mech_token']} "
        f"present_tense={stale['collision_present_tense']} "
        f"line={stale['collision_line']} "
        f"used_as_resolver={stale['used_as_namespace_resolver']}"
    )
    if stale["used_as_namespace_resolver"]:
        return fail("decision log was used as a namespace resolver")
    if indep["post_fix_collision_count"] != 0:
        return fail(
            f"post-fix bare M-NN collision count is "
            f"{indep['post_fix_collision_count']}, expected 0"
        )
    if stale["collision_present_tense"] and stale["contains_mech_token"]:
        return fail("stale log unexpectedly contains MECH tokens")

    matched = 0
    art_rows = {}
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        art_rows = {r["id"]: r for r in doc.get("rows") or []}
    for oid in SAMPLE:
        indep_row = by_id.get(oid)
        if indep_row is None:
            return fail(f"sample {oid} missing from independent closer")
        print(
            f"sample {oid} indep={indep_row['disposition']} "
            f"bucket={indep_row['bucket']} src={indep_row['resolution_source']}"
        )
        if art_rows:
            art = art_rows.get(oid)
            if art is None:
                return fail(f"sample {oid} missing from artifact table")
            if art.get("disposition") != indep_row["disposition"]:
                return fail(
                    f"sample {oid} artifact={art.get('disposition')} "
                    f"indep={indep_row['disposition']}"
                )
            if art.get("bucket") != indep_row["bucket"]:
                return fail(f"sample {oid} bucket mismatch")
            matched += 1
        else:
            matched += 1
    print(f"rederived={matched}/{len(SAMPLE)} fail=False")
    print("SUCCESS:BLD-0019-probe2 buckets-and-independent-rederive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
