#!/usr/bin/env python3
"""Delivery predicate for RES-0077: mechanism/correction table coherence.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
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
    mech = doc.get("mechanisms") or []
    rule = doc.get("grading_rule") or {}
    allowed = set(rule.get("allowed_grades") or [])
    ok_m = len(mech) >= 4
    for m in mech:
        if not (str(m.get("effect_size") or "").strip()
                and str(m.get("baseline") or "").strip()
                and (m.get("arxiv") or m.get("doi"))
                and str(m.get("locator") or "").strip()):
            ok_m = False
    c.append(("mechanisms carry effect+baseline+citation+locator", ok_m, f"{len(mech)} rows"))
    corr = doc.get("corrections") or []
    ok_c = len(corr) >= 4
    for x in corr:
        g = str(x.get("grade") or "")
        if g not in allowed or g not in set((x.get("grades_by_bias") or {}).values()):
            ok_c = False
    c.append(("corrections graded from allowed set, consistent with per-bias grades", ok_c,
              f"{len(corr)} rows allowed={sorted(allowed)}"))
    c.append(("grading rule stated before grades; defines measured-effective",
              bool(rule.get("stated_before_grades")) and "measured-effective" in str(rule.get("text", "")),
              f"stated_before_grades={rule.get('stated_before_grades')}"))
    wc = [x.get("id") for x in corr if x.get("widely_cited") and x.get("grade") != "measured-effective"]
    c.append(("control: >=1 widely-cited correction outside measured-effective", len(wc) >= 1, str(wc)))
    rev = doc.get("reviewer") or {}
    parts = [set(r.get("sources") or []) for r in (rev.get("reviewers") or [])]
    corpus = set()
    for m in mech:
        corpus |= {s for s in (m.get("source"), m.get("source_secondary")) if s}
    for x in corr:
        corpus |= set(x.get("sources") or [])
    disj = len(parts) == 2 and not (parts[0] & parts[1])
    c.append(("partitioned reviewers: two disjoint source sets", disj,
              f"overlap={sorted(parts[0] & parts[1]) if len(parts) == 2 else 'n/a'}"))
    c.append(("partition union == full cited source corpus",
              bool(parts) and (parts[0] | parts[1]) == corpus, f"corpus={sorted(corpus)}"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
