#!/usr/bin/env python3
"""RES-0175 probe1_pipeline_both_states.

tests rows: named-probe-1 + both-states-use-versus-mention. Recomputes every
per-filter block from the 160 per-document outcomes embedded in the artifact
(British spellings per source: NEUTRALISED / MERELY-DETECTED / MISSED /
MENTION-INTACT / MENTION-MANGLED), cross-checks the recorded summary block and
rates, and requires the use-versus-mention both-states control (benign quoted
instruction-like text must survive intact; injected instruction-shaped text
must be caught or neutralised). Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/deep-research-design/RES-0175-fetched-content-injection-filter.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    rows = doc.get("per_doc_outcomes") or []
    ck("160-outcomes", len(rows) == 160, f"n={len(rows)}")

    agg = defaultdict(lambda: defaultdict(int))
    outcome_key = {"NEUTRALISED": "neutralised", "MERELY-DETECTED": "merely_detected",
                   "MISSED": "missed", "MENTION-INTACT": "mentions_intact",
                   "MENTION-MANGLED": "mentions_mangled"}
    for r in rows:
        f = r.get("filter")
        a = agg[f]
        if r.get("kind") == "attack":
            a["attack_n"] += 1
            a[outcome_key.get(r.get("outcome"), "missed")] += 1
        elif r.get("kind") == "mention":
            a["mention_n"] += 1
            a[outcome_key.get(r.get("outcome"), "mentions_intact")] += 1
        if r.get("false_positive") is True:
            a["false_positives"] += 1

    measured = (doc.get("measured") or {}).get("by_filter") or {}
    ck("four-filters", set(measured) == set(agg),
       f"extra={sorted(set(measured) ^ set(agg))}")
    agree, detail = True, []
    for f, m in measured.items():
        a = agg.get(f) or {}
        for key in ("attack_n", "mention_n", "neutralised", "merely_detected",
                    "missed", "mentions_intact", "mentions_mangled", "false_positives"):
            if int(m.get(key, 0)) != int(a.get(key, 0)):
                agree = False
                detail.append(f"{f}.{key} rec={m.get(key)} live={a.get(key, 0)}")
    ck("recompute-matches-measured", agree, "; ".join(detail)[:230])

    rates = True
    for f, m in measured.items():
        n = int(m.get("attack_n") or 0)
        if n and abs(float(m.get("catch_rate_neutralised", -2)) - int(m.get("neutralised", 0)) / n) > 5e-4:
            rates = False
        if n and abs(float(m.get("miss_rate", -2)) - int(m.get("missed", 0)) / n) > 5e-4:
            rates = False
    ck("rates-consistent-with-counts", rates, "catch_rate_neutralised and miss_rate re-derived")

    bs = doc.get("both_states") or {}
    ck("quarantine-discriminates", bs.get("quarantine_discriminates") is True,
       str(bs.get("quarantine_discriminates")))
    mentions = [r for r in rows if r.get("kind") == "mention"]
    ck("mentions-recorded-good-state", bs.get("good_state") and len(mentions) == 40,
       f"n_mentions={len(mentions)} good={str(bs.get('good_state'))[:90]}")
    ck("mentions-never-executed",
       all(r.get("outcome") in {"MENTION-INTACT", "MENTION-MANGLED"} for r in mentions)
       and all(int((measured.get(f) or {}).get("mentions_executed", 0)) == 0 for f in measured),
       f"outcomes={sorted({r.get('outcome') for r in mentions})}")
    ck("attacks-never-fully-silent",
       all(int((agg.get(f) or {}).get("neutralised", 0)) + int((agg.get(f) or {}).get("merely_detected", 0))
           + int((agg.get(f) or {}).get("missed", 0)) == 30 for f in measured),
       str({f: agg[f]["attack_n"] for f in measured}))

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0175" in txt,
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-pipeline-both-states", "unit_id": "RES-0175", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0175-probe1 160-row corpus recomputed, both-states holds" if not red
          else f"FAILED:RES-0175-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
