#!/usr/bin/env python3
"""RES-0111 delivery predicate: primitive-to-failure-class mapping closure.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0111"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    mp = doc.get("primitive_to_failure_class_mapping") or []
    named = doc.get("named_primitives") or []
    spec = doc.get("spec_failure_classes") or []
    spec_ids = {s.get("id") for s in spec}
    c.append(("every named primitive appears exactly once in the mapping",
              sorted(r.get("primitive") for r in mp) == sorted(named) and len(named) == len(mp),
              f"named={len(named)} rows={len(mp)}"))
    dropped_rows = [r for r in mp if str(r.get("decision")).upper() == "DROPPED"]
    mapped_rows = [r for r in mp if str(r.get("decision")).upper() == "MAPPED"]
    c.append(("DROPPED count matches primitives_dropped_unmapped_count and the dropped register",
              len(dropped_rows) == int(doc.get("primitives_dropped_unmapped_count") or -1)
              and sorted(r.get("primitive") for r in dropped_rows)
              == sorted(d.get("primitive") for d in doc.get("dropped") or []),
              f"dropped_rows={len(dropped_rows)} recorded={doc.get('primitives_dropped_unmapped_count')}"))
    bad = [r.get("primitive") for r in mapped_rows if r.get("failure_class_id") not in spec_ids]
    c.append(("every MAPPED primitive names a failure class from the spec list", not bad,
              f"off-list={bad}"))
    covered = {r.get("failure_class_id") for r in mapped_rows}
    uncovered = doc.get("uncovered_spec_classes") or []
    c.append(("coverage closure: mapped classes + uncovered == all spec classes",
              covered | set(uncovered) == spec_ids and not (covered & set(uncovered)),
              f"covered={sorted(x for x in covered if x)} uncovered={uncovered}"))
    unc_reason = str(doc.get("uncovered_spec_class_reason") or "").strip()
    c.append(("each uncovered spec class carries a stated reason",
              all(u in unc_reason or True for u in uncovered) and len(unc_reason) > 0
              and all(str(u) in unc_reason for u in uncovered),
              unc_reason[:80]))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
