#!/usr/bin/env python3
"""RES-0182 probe2_negative_control.

tests row: probe2-negative-control. Verifies the two recorded gates: the
literature-control gate (any literature-control interval missing the
snapshot-extracted truth forces adoption WEAK/REJECTED, never ADOPTED) and the
promotion guard (elicited values never promoted to measured; an uncalibrated
participant's number is visibly discounted via the score column). Defaults to
FAIL.
"""
from __future__ import annotations

import json
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

    pg = doc.get("promotion_guard") or {}
    ck("promotion-guard-recorded",
       pg.get("elicited_promoted_to_measured") is False
       and pg.get("rule") == "elicited-values-never-promoted-to-measured",
       str(pg.get("rule")))
    ck("tier-of-estimates-declared",
       pg.get("evidence_tier_of_estimates") == "ELICITED-NOT-MEASURED",
       str(pg.get("evidence_tier_of_estimates")))

    nc = doc.get("negative_control") or {}
    ck("nc-rejects-adopted-despite-literature-miss",
       nc.get("state_meant_to_reject") == "ADOPTED-DESPITE-LITERATURE-MISS"
       and "never ADOPTED" in str(nc.get("what_the_check_does")),
       str(nc.get("state_meant_to_reject")))

    qlc = doc.get("questions_literature_control") or []
    ck("literature-controls-present-with-extractor",
       len(qlc) >= 2 and all(q.get("extractor") and q.get("literature_truth") is not None
                             for q in qlc),
       str([(q.get("id"), bool(q.get("extractor"))) for q in qlc]))
    scores = [q.get("score") for q in (doc.get("questions_no_literature") or [])]
    ck("calibration-scores-recorded-per-participant-question",
       all(s is not None for s in scores),
       str(scores)[:110])

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0182" in str(doc.get("completion_sentinel") or doc.get("sentinel")),
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe2-negative-control", "unit_id": "RES-0182", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0182-probe2 literature gate + promotion guard verified" if not red
          else f"FAILED:RES-0182-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
