#!/usr/bin/env python3
"""WFA-0123 qualify_a -- three-way AND, Jaccard collapse + SPDX licence files.

Method A as recorded in WFA-0123-candidate-floor-proof.json: alias collapse
(aliases field), duplicate collapse (Jaccard over mechanism token sets >= 0.8),
then AND over classification (present, not UNKNOWN-NEEDS-PROBE), resolved
provenance (recorded file exists on disk) and fetched licence (recorded
LICENSE/COPYING file exists and carries an SPDX-License-Identifier).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def jaccard(a: str, b: str) -> float:
    ta, tb = set(re.findall(r"[a-z0-9]+", a.lower())), set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def spdx_ok(licence_file: str | None) -> bool:
    if not licence_file:
        return False
    p = REPO / licence_file
    if not p.is_file():
        return False
    head = p.read_text(encoding="utf-8", errors="replace")[:400]
    return bool(re.search(r"SPDX-License-Identifier:\s*[A-Za-z0-9.-]+", head))


def classify_row(row: dict) -> bool:
    c = str(row.get("classification") or "")
    return bool(c) and c != "UNKNOWN-NEEDS-PROBE"


def provenance_ok(row: dict) -> bool:
    pf = row.get("provenance_file")
    return bool(pf) and (REPO / pf).is_file()


def run(records: list[dict]) -> dict:
    raw = [r for r in records]
    excluded = {"alias": [], "duplicate": [], "trivial_fork": []}
    seen = []
    survivors = []
    for r in raw:
        alias_hit = False
        for s in survivors:
            if r.get("id") in (s.get("aliases") or []) or s.get("id") in (r.get("aliases") or []):
                excluded["alias"].append(r["id"])
                alias_hit = True
                break
        if alias_hit:
            continue
        dup_hit = False
        for s in survivors:
            if jaccard(r.get("mechanism") or "", s.get("mechanism") or "") >= 0.8:
                excluded["duplicate"].append(r["id"])
                dup_hit = True
                break
        if dup_hit:
            continue
        survivors.append(r)
    qualified = []
    and_rejected = []
    for r in survivors:
        if classify_row(r) and provenance_ok(r) and spdx_ok(r.get("licence_file")):
            qualified.append(r["id"])
        else:
            and_rejected.append(r["id"])
    return {
        "method": "qualify-a-jaccard-spdx",
        "raw_count": len(raw),
        "excluded": excluded,
        "excluded_counts": {k: len(v) for k, v in excluded.items()},
        "after_collapse": len(survivors),
        "and_rejected_count": len(and_rejected),
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
