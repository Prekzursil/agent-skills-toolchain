#!/usr/bin/env python3
"""RES-0176 probe1_two_rails.

tests row: probe1-quotes-two-rails-hardness. Verifies from the artifact's own
data: three frameworks covered; five load-bearing claims each naming the
canonical mechanism separately from the runtime that hosts it, with two
independent rails (source lineage entries with resolved provenance) and a
Sherman-Kent band; hardness rows are exclusive to one framework each.
Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/teardown/RES-0176-teardown-graph-vs-role-frameworks.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:240]})
        return bool(ok)

    fws = doc.get("frameworks") or []
    fids = [f.get("id") or f.get("name") for f in fws]
    ck("three-frameworks", len(fws) == 3 and set(fids) == {"langgraph", "crewai", "autogen"},
       str(fids))

    claims = doc.get("claims") or []
    ck("five-claims", len(claims) == 5, f"n={len(claims)}")
    ck("mechanism-separated-from-runtime",
       all(c.get("canonical_mechanism") and (c.get("makes_easy") or c.get("quoted_mechanism"))
           for c in claims),
       str([c.get("claim_id") for c in claims]))
    ck("claims-two-rails-lineage",
       all(len(c.get("source_lineage") or []) >= 2
           and all(s.get("resolved_url") or s.get("canonical_url") for s in (c.get("source_lineage") or []))
           for c in claims),
       str([len(c.get("source_lineage") or []) for c in claims]))
    ck("claims-sherman-kent-band",
       all(c.get("sherman_kent_band") in {"highly probable", "probable", "even odds",
                                          "doubtful", "highly doubtful"}
           for c in claims),
       str([c.get("sherman_kent_band") for c in claims]))
    ck("claims-independent-verification-path",
       all(str(c.get("independent_verification_path") or "").strip() for c in claims),
       "named path per claim")

    tv = doc.get("transfer_verdicts") or []
    ck("three-transfer-verdicts", len(tv) == 3,
       str([(t.get("abstraction"), t.get("transferable")) for t in tv]))
    ck("verdicts-name-cost-on-our-control-plane",
       all(str(t.get("reimplementation_cost") or "").strip() and t.get("runtime_host")
           for t in tv),
       str([t.get("abstraction") for t in tv]))

    h = doc.get("hardness") or {}
    rows = h.get("rows") or []
    ck("hardness-all-exclusive-flag", h.get("all_exclusive") is True,
       f"all_exclusive={h.get('all_exclusive')}")
    owners = Counter(str(r.get("owner")) for r in rows)
    ck("hardness-rows-have-owner-and-exclusive",
       all(r.get("owner") in {"langgraph", "crewai", "autogen"} and r.get("exclusive") is True
           for r in rows),
       str(dict(owners)))

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0176",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-two-rails", "unit_id": "RES-0176", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0176-probe1 two rails + hardness exclusivity verified" if not red
          else f"FAILED:RES-0176-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
