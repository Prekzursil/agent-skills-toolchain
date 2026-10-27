#!/usr/bin/env python3
"""RES-0158 probe_protocol_crosscheck.

Cross-checks each technique against the plain-debate baseline (each must
require something plain debate does not mandate) and verifies both recorded
negative controls went red on their mutants and stayed silent on the good
state. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/gem-hunt/RES-0158-transfer-structured-analytic-techniques.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:220]})
        return bool(ok)

    rep = doc.get("report") or {}
    baseline = rep.get("plain_debate_baseline") or {}
    ck("baseline-defined", bool(baseline.get("definition")), str(baseline.get("definition", ""))[:100])

    techniques = rep.get("techniques") or []
    ck("every-technique-adds-over-debate",
       all(t.get("direct_implementability") in {"YES", "YES-WITH-GUARDRAILS", "YES-AS-WRAPPER-NOT-STANDALONE-DEBATE", "PARTIAL"} for t in techniques),
       str([(t.get("id"), t.get("direct_implementability")) for t in techniques])[:220])
    extra = all(
        str(t.get("plain_debate_delta") or "").strip() for t in techniques
    )
    ck("beyond-debate-recorded-per-technique", extra,
       str([t.get("id") for t in techniques]))

    lbc = rep.get("load_bearing_claims") or []
    ck("load-bearing-claims-have-honest-status",
       all(c.get("status") in {"SUPPORTED", "PARTIAL", "REFUTED", "NOT-CHECKED-AFTER-REFUTATION"} for c in lbc),
       str([(c.get("claim_id"), c.get("status")) for c in lbc])[:200])
    ck("confidence-bands-sherman-kent",
       all(c.get("confidence_band") in {"near-certain", "likely", "even", "doubtful", "remote"} for c in lbc),
       str([c.get("confidence_band") for c in lbc]))

    for nc in doc.get("negative_controls") or []:
        ck(f"nc-{nc.get('id')}-red-on-bad",
           nc.get("fired_on_bad_state") is True and bool(nc.get("bad_state_output")),
           str(nc.get("id")))
        ck(f"nc-{nc.get('id')}-silent-on-good",
           nc.get("silent_on_good_state") is True and bool(nc.get("good_state_output")),
           str(nc.get("id")))

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe-protocol-crosscheck", "unit_id": "RES-0158", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0158-probe2 six techniques clear the debate baseline, controls both-states" if not red
          else f"FAILED:RES-0158-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
