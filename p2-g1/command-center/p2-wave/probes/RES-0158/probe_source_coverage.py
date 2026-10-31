#!/usr/bin/env python3
"""RES-0158 probe_source_coverage.

tests row: "Fetch and hash all primary and failure-mode sources". Re-verifies
from the artifact's embedded source_lineage: 15 sources, each with byte count,
sha256, resolved URL and fetch timestamp; each of the six assessed techniques
cites at least one primary methodological source and one documented failure
mode; claim-to-source overlap per technique. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/gem-hunt/RES-0158-transfer-structured-analytic-techniques.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:220]})
        return bool(ok)

    rep = doc.get("report") or {}
    lineage = rep.get("source_lineage") or []
    ck("fifteen-sources-with-lineage", len(lineage) == 15, f"n={len(lineage)}")
    ok_fields = all(
        s.get("resolved_url") and s.get("sha256") and s.get("fetch_timestamp") and s.get("bytes")
        for s in lineage
    )
    ck("every-source-url-sha-timestamp", ok_fields,
       str([bool(s.get("sha256")) for s in lineage]))
    ck("sha256-shape-valid", all(len(str(s.get("sha256"))) == 64 for s in lineage), "sha256[64]")

    techniques = rep.get("techniques") or []
    tids = [t.get("id") for t in techniques]
    ck("six-techniques-assessed", len(techniques) == 6, str(tids))
    # each technique cites >=1 primary methodological source and >=1 documented
    # failure-mode source, both resolving into the lineage table
    lids = {s.get("id") for s in lineage}
    ma = all(any(sid in lids for sid in (t.get("primary_source_ids") or [])) for t in techniques)
    fa = all(any(sid in lids for sid in (t.get("failure_source_ids") or [])) for t in techniques)
    ck("method-anchors-present", ma,
       str([(t.get("id"), [s in lids for s in (t.get("primary_source_ids") or [])]) for t in techniques])[:200])
    ck("failure-anchors-present", fa,
       str([(t.get("id"), bool(t.get("documented_failure_mode"))) for t in techniques])[:200])

    lbc = rep.get("load_bearing_claims") or []
    ck("claims-two-signal",
       all(c.get("two_signal_verification") and c.get("named_independent_verification_path") for c in lbc),
       str([c.get("claim_id") for c in lbc]))
    # claim-to-source overlap: each claim cites >=1 lineage id that exists
    lids = {s.get("id") for s in lineage}
    cites_ok = all(
        any(x.get("id") in lids for x in (c.get("source_lineage") or []))
        for c in lbc
    )
    ck("claims-cite-existing-lineage", cites_ok, f"n_claims={len(lbc)}")
    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0158" in txt, f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe-source-coverage", "unit_id": "RES-0158", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0158-probe1 15 hashed sources, six techniques anchored" if not red
          else f"FAILED:RES-0158-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
