#!/usr/bin/env python3
"""RES-0089 delivery predicate: detector table FP-rate coverage.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0089"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    dt = doc.get("detector_table") or []
    c.append(("detector table has >=6 rows", len(dt) >= 6, f"n={len(dt)}"))
    ok_ev = all(str(r.get("effect_size") or "").strip() and str(r.get("baseline") or "").strip()
                and str(r.get("section_or_figure") or "").strip()
                and (r.get("arxiv") or r.get("doi") or r.get("paper_id")) for r in dt)
    c.append(("every row carries effect+baseline+section+citation", ok_ev, f"{len(dt)} rows"))
    unmeasured = sorted(r["id"] for r in dt
                        if str(r.get("false_positive_rate") or "").upper() == "UNMEASURED")
    recorded = sorted(doc.get("answer", {}).get("false_positive_unmeasured") or [])
    c.append(("UNMEASURED marks match the answer's false_positive_unmeasured set",
              unmeasured == recorded, f"table={unmeasured}"))
    ans = doc.get("answer") or {}
    may_disq = sorted(r["id"] for r in dt if r.get("may_disqualify_a_result"))
    c.append(("only measured-FP detectors may disqualify a result",
              may_disq == sorted(ans.get("can_disqualify_a_result") or [])
              and all(str(r.get("false_positive_rate")).upper() != "UNMEASURED"
                      for r in dt if r.get("may_disqualify_a_result")),
              f"may_disqualify={may_disq}"))
    ids = {r["id"] for r in dt}
    shown = ans.get("shown_to_work") or []
    c.append(("shown_to_work subset of table ids", set(shown) <= ids, f"{len(shown)} rows"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
