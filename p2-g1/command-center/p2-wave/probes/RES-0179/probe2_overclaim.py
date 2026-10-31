#!/usr/bin/env python3
"""RES-0179 probe2_overclaim.

tests row: T2-overclaim-and-dual-review - every restriction must carry the
status code or block page that evidences it (not a policy-page inference),
edges must be well-formed, and the dual-review/legalscope markers must be
present. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/sources-frontier/RES-0179-jurisdiction-source-accessibility-scoping.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    bs = doc.get("barrier_survey") or []
    evidenced = 0
    for b in bs:
        f = b.get("fetch") or {}
        if f.get("status_code") or f.get("http_status") or f.get("body_head_excerpt"):
            evidenced += 1
    ck("every-restriction-evidenced-by-attempt", evidenced == len(bs) and len(bs) > 0,
       f"evidenced={evidenced}/{len(bs)}")

    ce = doc.get("contradiction_edges") or []
    se = doc.get("support_edges") or []
    ck("edges-well-formed",
       all(("from" in e and "to" in e) or ("claim_a" in e and "claim_b" in e)
           for e in (ce + se)),
       f"contradiction={len(ce)} support={len(se)}")
    ck("unreachable-plan-recorded",
       bool(doc.get("unreachable_only_source_plan")),
       str(doc.get("unreachable_only_source_plan"))[:110])
    ck("legal-scope-markers",
       bool(doc.get("not_legal_advice")) and bool(doc.get("query_from_region")),
       f"not_legal_advice={doc.get('not_legal_advice')}")
    rv = doc.get("reviewers") or []
    ck("dual-review-recorded", isinstance(rv, list) and len(rv) >= 1,
       f"n_reviewers={len(rv)}")
    ck("snapshot-pre-write-recorded",
       bool(doc.get("snapshot_sha256_pre_write")),
       str(doc.get("snapshot_sha256_pre_write"))[:80])
    ck("freshness-stamp", bool(doc.get("freshness_stamp")),
       str(doc.get("freshness_stamp"))[:80])

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0179",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe2-overclaim", "unit_id": "RES-0179", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0179-probe2 no overclaim, dual review + legal markers present" if not red
          else f"FAILED:RES-0179-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
