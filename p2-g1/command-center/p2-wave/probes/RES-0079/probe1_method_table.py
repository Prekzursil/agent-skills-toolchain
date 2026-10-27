#!/usr/bin/env python3
"""RES-0079 delivery predicate: method table with prerequisite-data column.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
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
    c.append(("method table has >=3 methods", len(mt) >= 3, f"n={len(mt)}"))
    c.append(("every row carries the prerequisite-data column",
              all(COL in r and str(r[COL]).strip() for r in mt),
              f"rows={len(mt)}"))
    zero = [r for r in mt if str(r.get("usable_at_zero_history")) == "True"]
    today = [r for r in mt if str(r.get("usable_today")) == "True"]
    ans = doc.get("answer") or {}
    zid = ans.get("zero_history_method_id")
    c.append(("exactly one method usable at zero history and usable today",
              len(zero) == 1 and len(today) == 1 and zero[0]["id"] == today[0]["id"] == zid,
              f"zero={[r['id'] for r in zero]} today={[r['id'] for r in today]} zid={zid}"))
    c.append(("answer states the with-history and without-history picks",
              bool(str(ans.get("with_labelled_history") or ""))
              and bool(str(ans.get("without_labelled_history_today") or "")),
              f"with={str(ans.get('with_labelled_history'))[:60]}"))
    rev = doc.get("reviewer") or {}
    c.append(("adversarial-refuter verdict recorded at artifact level",
              str(rev.get("verdict")) == "PASS" and rev.get("independent") is True,
              f"verdict={rev.get('verdict')}"))
    cl = doc.get("claims") or []
    c.append(("claims carry source lineage (work/section/doi)",
              len(cl) >= 2 and all(x.get("source_lineage") for x in cl),
              f"n_claims={len(cl)}"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
