#!/usr/bin/env python3
"""RES-0111 independent re-derivation: promoted mappings carry full citations.
NC = stripping a baseline from a promoted row must fire the detector."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0111"

def evidence_gaps(rows):
    gaps = []
    for r in rows:
        if str(r.get("decision")).upper() != "MAPPED":
            continue
        rid = str(r.get("primitive"))
        promoted = bool(r.get("promoted"))
        # recorded rule (tests_required): PROMOTED mechanisms need DOI,
        # section/figure, effect size AND baseline; non-promoted MAPPED rows
        # still need a citation and a section.
        if not (str(r.get("doi") or "").strip() or str(r.get("arxiv_id") or "").strip()):
            gaps.append(rid + ":no-doi-or-arxiv")
        if not str(r.get("section_or_figure") or "").strip():
            gaps.append(rid + ":no-section")
        if promoted and (not str(r.get("effect_size") or "").strip()
                         or not str(r.get("baseline") or "").strip()):
            gaps.append(rid + ":effect-without-baseline")
        lin = r.get("source_lineage") or {}
        if promoted and isinstance(lin, dict) and not str(lin.get("snapshot_sha256") or "").strip():
            gaps.append(rid + ":no-snapshot-sha")
    return gaps

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    mp = doc.get("primitive_to_failure_class_mapping") or []
    mapped = [r for r in mp if str(r.get("decision")).upper() == "MAPPED"]
    promoted = [r for r in mapped if r.get("promoted")]
    c.append((">=3 primitives MAPPED with full evidence, >=1 promoted",
              len(mapped) >= 3 and len(promoted) >= 1,
              f"mapped={len(mapped)} promoted={len(promoted)}"))
    gaps = evidence_gaps(mp)
    c.append(("recomputed evidence rule: zero gaps on the delivered table", not gaps,
              f"gaps={gaps[:4]}"))

    def mutate(d):
        for r in d["primitive_to_failure_class_mapping"]:
            if r.get("promoted"):
                r["baseline"] = ""
                break
        return d

    mp2 = L.mutation_copy(doc, mutate)
    try:
        mdoc = json.loads(mp2.read_text(encoding="utf-8"))
        fired = bool(evidence_gaps(mdoc["primitive_to_failure_class_mapping"]))
        c.append(("NC: promoted row stripped of its baseline fires the detector", fired,
                  f"mutant gaps={evidence_gaps(mdoc['primitive_to_failure_class_mapping'])[:2]}"))
    finally:
        mp2.unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
