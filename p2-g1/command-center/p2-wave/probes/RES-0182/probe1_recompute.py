#!/usr/bin/env python3
"""RES-0182 probe1_recompute.

tests row: probe1-recompute. Re-derives the equal-weight pooled quantiles for
every no-literature question from its participant rows embedded in the
artifact (median-of-quantiles), matches them against the recorded aggregation,
and verifies the honest information-over-NOT-FOUND verdict: elicitation adds a
LABELED PRIOR, not measured evidence. Defaults to FAIL.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/sources-frontier/RES-0182-expert-elicitation-as-a-source-class.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    qs = doc.get("questions_no_literature") or []
    ck("six-questions", len(qs) == 6, f"n={len(qs)}")
    ck("elicited-tier-honest",
       all(q.get("evidence_tier") == "ELICITED-NOT-MEASURED" for q in qs),
       str(sorted({q.get("evidence_tier") for q in qs})))
    ck("nothing-promoted-to-measured",
       all(q.get("promoted_to_measured") is False for q in qs),
       str([q.get("promoted_to_measured") for q in qs]))

    agree = True
    detail = []
    for q in qs:
        agg = q.get("aggregation") or {}
        rows = agg.get("participant_rows") or []
        if not rows:
            agree = False
            detail.append(f"{q.get('id')}: no participant rows")
            continue
        # independent median-of-quantiles recompute
        q05 = statistics.median([float(r["q05"]) for r in rows if r.get("q05") is not None])
        q50 = statistics.median([float(r["q50"]) for r in rows if r.get("q50") is not None])
        q95 = statistics.median([float(r["q95"]) for r in rows if r.get("q95") is not None])
        ew = agg.get("equal_weight") or {}
        if (abs(q05 - float(ew.get("q05", 1e9))) > 1e-6
                or abs(q50 - float(ew.get("q50", 1e9))) > 1e-6
                or abs(q95 - float(ew.get("q95", 1e9))) > 1e-6):
            agree = False
            detail.append(f"{q.get('id')}: rec=({q05:.2f},{q50:.2f},{q95:.2f}) "
                          f"recorded=({ew.get('q05')},{ew.get('q50')},{ew.get('q95')})")
    ck("equal-weight-quantiles-recompute", agree, "; ".join(detail)[:230])

    io = doc.get("information_over_not_found") or {}
    ck("labeled-prior-emitted-not-measured-evidence",
       io.get("labeled_prior_emitted") is True and io.get("adds_measured_evidence") is False,
       json.dumps({k: io.get(k) for k in ("labeled_prior_emitted", "adds_measured_evidence")}))
    ck("search-not-beaten-as-source-class",
       io.get("beats_search_as_source_class") is False,
       str(io.get("beats_search_as_source_class")))
    ck("honest-note-carried",
       "not evidence" in str(io.get("note", "")).lower(),
       str(io.get("note"))[:110])

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0182" in str(doc.get("completion_sentinel") or doc.get("sentinel")),
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-recompute", "unit_id": "RES-0182", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0182-probe1 pooled quantiles re-derived, honest tier carried" if not red
          else f"FAILED:RES-0182-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
