#!/usr/bin/env python3
"""RES-0077 independent re-derivation + mutation negative control.
Recreated 2026-10-25 (wave-2 shard 17): re-derives partition invariants with
a second mechanic and proves the detector fires on a mutant."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0077"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    parts = [set(r.get("sources") or []) for r in ((doc.get("reviewer") or {}).get("reviewers") or [])]
    c.append(("re-derived partitions disjoint", len(parts) == 2 and not (parts[0] & parts[1]),
              f"overlap={sorted(parts[0] & parts[1]) if len(parts) == 2 else 'n/a'}"))
    per_bias = {}
    for x in doc.get("corrections") or []:
        gb = x.get("grades_by_bias") or {}
        g = str(x.get("grade") or "")
        ok = bool(gb) and all(str(v) in ("measured-effective", "proposed-only", "refuted") for v in gb.values())
        per_bias[x.get("id")] = ok
    c.append(("every correction maps >=1 named bias to an allowed grade", all(per_bias.values()),
              f"{per_bias}"))
    rows = doc.get("bias_by_correction_table") or {}
    c.append(("bias-by-correction table present", bool(rows), f"keys={len(rows)}"))

    def mutate(d):
        rs = d["reviewer"]["reviewers"]
        cross = sorted(set(rs[1].get("sources") or []))[0]
        rs[0]["sources"].append(cross)
        return d

    mp = L.mutation_copy(doc, mutate)
    try:
        mdoc = json.loads(mp.read_text(encoding="utf-8"))
        ms = [set(r.get("sources") or []) for r in mdoc["reviewer"]["reviewers"]]
        c.append(("NC: cross-partition source move fires the overlap detector",
                  bool(ms[0] & ms[1]), f"mutant overlap={sorted(ms[0] & ms[1])}"))
    finally:
        mp.unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
