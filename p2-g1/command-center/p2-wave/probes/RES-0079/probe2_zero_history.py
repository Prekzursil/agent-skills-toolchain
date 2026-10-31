#!/usr/bin/env python3
"""RES-0079 independent re-derivation: the zero-history pick and NC."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0079"
COL = "prerequisite-data"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    mt = doc.get("method_table") or []
    zid = (doc.get("answer") or {}).get("zero_history_method_id")
    row = next((r for r in mt if r.get("id") == zid), None)
    pre = str((row or {}).get(COL) or "").lower()
    c.append(("zero-history row's prerequisite is current data only",
              row is not None and "labelled" not in pre and "history" not in pre,
              f"method={zid} prereq={pre[:70]}"))
    others = [r for r in mt if r.get("id") != zid]
    blocked = [r for r in others
               if "label" in str(r.get(COL) or "").lower() or "history" in str(r.get(COL) or "").lower()]
    c.append(("every other method is blocked on labelled history",
              len(blocked) == len(others), f"blocked={[r['id'] for r in blocked]}"))
    c1 = next((x for x in doc.get("claims") or [] if x.get("claim_id") == "RES-0079-C1"), None)
    lin = ((c1 or {}).get("source_lineage") or [{}])[0]
    c.append(("zero-history lineage cites Stone 1961 opinion pool",
              "stone" in str(lin.get("work") or "").lower()
              and str(lin.get("doi") or "").startswith("10.1214"),
              f"work={lin.get('work')} doi={lin.get('doi')}"))
    cav = str((c1 or {}).get("strongest_caveat") or "")
    c.append(("caveat names the Ranjan-Gneiting uncalibrated-linear-pool result",
              "ranjan" in cav.lower() and "uncalibrated" in cav.lower(), cav[:80]))

    def mutate(d):
        for r in d["method_table"]:
            if r["id"] in ("log-equal", "bayesian-bma"):
                r["usable_at_zero_history"] = "True"
        return d

    mp = L.mutation_copy(doc, mutate)
    try:
        mdoc = json.loads(mp.read_text(encoding="utf-8"))
        n_zero = sum(1 for r in mdoc["method_table"]
                     if str(r.get("usable_at_zero_history")) == "True")
        c.append(("NC: two extra zero-history rows break the uniqueness detector",
                  n_zero > 1, f"mutant zero-history rows={n_zero}"))
    finally:
        mp.unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
