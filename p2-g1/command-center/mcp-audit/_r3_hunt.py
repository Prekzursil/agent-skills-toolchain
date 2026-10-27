#!/usr/bin/env python3
"""Round-3 adversarial hunt: does the SHIPPED prose still agree with the SHIPPED data?

Round 2 regenerated ``disposition.json`` from a fresh sweep (``capability-matrix-r2.json``)
while the narrative artifacts kept round-1 figures.  This walks every number that appears in
both places and reports the disagreements, rather than asserting there are none.

Read-only.  Run::  python _r3_hunt.py
"""

from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
DOCS = REPO / "docs" / "mcp-audit"


def load(p: pathlib.Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def totals(matrix: dict) -> dict:
    rows = [r for r in matrix["rows"] if r.get("call_verified")]
    return {
        "verified": len(rows),
        "tools": sum(r.get("tool_count") or 0 for r in rows),
        "name_bytes": sum(r.get("name_bytes") or 0 for r in rows),
        "schema_bytes": sum(r.get("schema_bytes") or 0 for r in rows),
    }


def main() -> int:
    m1 = load(HERE / "capability-matrix.json")
    m2 = load(HERE / "capability-matrix-r2.json")
    disp = load(HERE / "disposition.json")

    t1, t2 = totals(m1), totals(m2)
    print("== cost totals over handshake-verified rows ==")
    for k in ("verified", "tools", "name_bytes", "schema_bytes"):
        flag = "" if t1[k] == t2[k] else "   <-- DIFFERS"
        print(f"  {k:13s} r1={t1[k]:>8}  r2={t2[k]:>8}{flag}")

    print("\n== which matrix did disposition.json come from? ==")
    print(f"  disposition.source_matrix = {disp.get('source_matrix')!r}")
    per1 = {
        r["name"]: r.get("schema_bytes") for r in m1["rows"] if r.get("call_verified")
    }
    per2 = {
        r["name"]: r.get("schema_bytes") for r in m2["rows"] if r.get("call_verified")
    }
    perd = {
        r["name"]: r.get("schema_bytes") for r in disp["rows"] if r.get("schema_bytes")
    }
    match1 = sum(1 for k, v in perd.items() if per1.get(k) == v)
    match2 = sum(1 for k, v in perd.items() if per2.get(k) == v)
    print(f"  rows whose schema_bytes match r1: {match1}/{len(perd)}")
    print(f"  rows whose schema_bytes match r2: {match2}/{len(perd)}")

    print("\n== per-row schema_bytes drift r1 -> r2 ==")
    for name in sorted(set(per1) | set(per2)):
        a, b = per1.get(name), per2.get(name)
        if a != b:
            print(f"  {name:22s} {a} -> {b}")

    print("\n== field coverage across all 23 disposition rows ==")
    for f in (
        "pid",
        "rss_bytes",
        "tool_count",
        "name_bytes",
        "schema_bytes",
        "last_error",
    ):
        n = sum(1 for r in disp["rows"] if r.get(f) is not None)
        print(f"  {f:13s} non-null on {n}/{len(disp['rows'])} rows")

    print("\n== numbers asserted in the narrative docs ==")
    pat = re.compile(
        r"(707|603,233|603233|11,645|11645|51\.8|321,053|321053|53\.2|60\.1)"
    )
    for md in sorted(DOCS.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        hits: dict[str, int] = {}
        for line in text.splitlines():
            for m in pat.finditer(line):
                hits[m.group(1)] = hits.get(m.group(1), 0) + 1
        if hits:
            print(f"  {md.name}: {hits}")

    print("\n== recomputed from the matrix disposition.json actually used ==")
    src = t2 if match2 >= match1 else t1
    ratio = src["schema_bytes"] / src["name_bytes"] if src["name_bytes"] else 0
    print(
        f"  tools={src['tools']} name_bytes={src['name_bytes']:,} "
        f"schema_bytes={src['schema_bytes']:,} ratio={ratio:.1f}x"
    )
    ch = next((r for r in disp["rows"] if r["name"] == "cloud-hub"), {})
    if ch.get("schema_bytes"):
        print(
            f"  cloud-hub schema share = "
            f"{100 * ch['schema_bytes'] / src['schema_bytes']:.1f}%  "
            f"({ch['schema_bytes']:,} B)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
