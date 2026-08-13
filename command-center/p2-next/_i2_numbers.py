"""Gather the exact, re-derived numbers the owner-facing doc must carry.

Reads NOTHING from a stored summary: every figure below is recomputed from the committed
tree through the shipped resolver, so a number that lands in the doc can be re-derived by
the gate that guards it.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "_vs", Path(__file__).with_name("vendor_satisfiability.py")
)
_vs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vs)

for basis in ("committed", "worktree"):
    rows = _vs.load_units(basis)
    c = Counter(r["verdict"] for r in rows)
    print(
        f"{basis:>9}: blocked={len(rows)} rail={c['RAIL_BLOCKED']} sat={c['SATISFIABLE_NOW']}"
    )
    if basis == "committed":
        sat_ids = sorted(r["id"] for r in rows if r["verdict"] == "SATISFIABLE_NOW")
        print(f"           SATISFIABLE ids: {sat_ids}")

cat = json.loads(
    _vs.batch_blobs("HEAD", [_vs.CATALOG_REL])[_vs.CATALOG_REL],
)
print(f"catalog work_units: {len(cat['work_units'])}")

split = json.loads((REPO / "command-center/p2-next/REVIEW-GATE-SPLIT.json").read_text())
print(f"REVIEW-GATE-SPLIT counts: {split['counts']}  basis={split.get('basis')}")

art = json.loads(
    (REPO / "command-center/p2-next/VENDOR-SATISFIABILITY.json").read_text()
)
print(
    f"VENDOR-SATISFIABILITY.json: basis={art['basis']} blocked={art['blocked_units']} "
    f"verdicts={art['verdict_counts']}"
)

# how many of the satisfiable ten actually carry an independent reviewer PASS
paths = {r["id"]: r["output_path"] for r in _vs.load_units("committed")}
blobs = _vs.batch_blobs("HEAD", [paths[i] for i in sat_ids])
n_pass = 0
for i in sat_ids:
    rec = json.loads(blobs[paths[i]])
    rv = rec.get("reviewer") or {}
    ok = str(rv.get("verdict", "")).upper() == "PASS" and rv.get("independent") is True
    n_pass += ok
    print(
        f"  {i}: reviewer.verdict={rv.get('verdict')} independent={rv.get('independent')}"
    )
print(f"satisfiable units carrying an independent PASS: {n_pass}/{len(sat_ids)}")
