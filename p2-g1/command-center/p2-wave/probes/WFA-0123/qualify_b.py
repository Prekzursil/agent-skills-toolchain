#!/usr/bin/env python3
"""WFA-0123 qualify_b -- three-way AND, difflib collapse + header-prefix licence.

Method B as recorded in WFA-0123-candidate-floor-proof.json: written from the
stopping-condition text alone, independent of qualify_a - difflib
SequenceMatcher duplicate collapse (ratio >= 0.92 on names) and licence via a
header-prefix parse (SPDX line or a well-known licence header) of the fetched
licence file. Does not import qualify_a.
"""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

HEADER_PREFIXES = ("SPDX-License-Identifier:", "Permission is hereby granted",
                   "Apache License", "GNU General Public License", "MIT License")


def licence_ok(licence_file: str | None) -> bool:
    if not licence_file:
        return False
    p = REPO / licence_file
    if not p.is_file():
        return False
    head = p.read_text(encoding="utf-8", errors="replace")[:400]
    return any(prefix in head for prefix in HEADER_PREFIXES)


def classify_ok(row: dict) -> bool:
    c = str(row.get("classification") or "")
    return bool(c) and c != "UNKNOWN-NEEDS-PROBE"


def provenance_ok(row: dict) -> bool:
    pf = row.get("provenance_file")
    return bool(pf) and (REPO / pf).is_file()


def run(records: list[dict]) -> dict:
    excluded = {"alias": [], "duplicate": [], "trivial_fork": []}
    survivors = []
    for r in records:
        drop = False
        for s in survivors:
            if r.get("id") in (s.get("aliases") or []) or s.get("id") in (r.get("aliases") or []):
                excluded["alias"].append(r["id"])
                drop = True
                break
            ratio = SequenceMatcher(None, r.get("name") or "", s.get("name") or "").ratio()
            if ratio >= 0.92:
                excluded["duplicate"].append(r["id"])
                drop = True
                break
        if not drop:
            survivors.append(r)
    qualified = []
    rejected = []
    for r in survivors:
        if classify_ok(r) and provenance_ok(r) and licence_ok(r.get("licence_file")):
            qualified.append(r["id"])
        else:
            rejected.append(r["id"])
    return {
        "method": "qualify-b-difflib-header-prefix",
        "raw_count": len(records),
        "excluded": excluded,
        "excluded_counts": {k: len(v) for k, v in excluded.items()},
        "after_collapse": len(survivors),
        "and_rejected_count": len(rejected),
        "qualified_count": len(qualified),
        "qualified_ids": qualified,
    }


def main() -> int:
    fx = json.loads((Path(__file__).parent / "fixtures" / "planted_registry.json")
                    .read_text(encoding="utf-8"))
    print(json.dumps(run(fx["records"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
