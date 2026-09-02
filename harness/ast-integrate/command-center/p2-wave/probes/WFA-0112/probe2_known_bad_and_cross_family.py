#!/usr/bin/env python3
"""Probe 2: every oracle rejects known-bad artifacts and other families' gold."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import case_id_for, mutant_blobs, mutant_filename, write_fixtures  # noqa: E402
from families import FAMILIES  # noqa: E402
from oracle import evaluate  # noqa: E402

FIXTURES = HERE / "fixtures"


def main() -> int:
    write_fixtures()
    fail = False
    rows = []
    for family in FAMILIES:
        fid = str(family["family_id"])
        cid = case_id_for(fid)
        gold = FIXTURES / fid / "good.json"
        gold_v = evaluate(gold, fid, cid)
        if not gold_v["accept"]:
            fail = True
        bad_hits = []
        for name, _blob in mutant_blobs(family):
            path = FIXTURES / fid / mutant_filename(name)
            v = evaluate(path, fid, cid)
            rejected = not v["accept"]
            bad_hits.append({"name": name, "rejected": rejected, "reasons": v["reasons"]})
            if not rejected:
                fail = True
        cross_leaks = []
        for other in FAMILIES:
            oid = str(other["family_id"])
            if oid == fid:
                continue
            v = evaluate(gold, oid, case_id_for(oid))
            if v["accept"]:
                fail = True
                cross_leaks.append(oid)
        rows.append(
            {
                "family_id": fid,
                "gold_accept": gold_v["accept"],
                "known_bad_rejected": all(h["rejected"] for h in bad_hits),
                "known_bad": bad_hits,
                "cross_family_leaks": cross_leaks,
            }
        )
    print(json.dumps({"probe": "probe2-known-bad-and-cross-family", "rows": rows}, indent=2, sort_keys=True))
    n_bad = sum(1 for r in rows if r["known_bad_rejected"])
    n_cross = sum(1 for r in rows if not r["cross_family_leaks"])
    print(f"families={len(rows)} known_bad_ok={n_bad} cross_family_ok={n_cross}")
    if fail:
        print("FAILED:WFA-0112-probe2 known-bad or cross-family leak")
        return 1
    print("SUCCESS:WFA-0112-probe2 every oracle rejected known-bad and other-family gold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
