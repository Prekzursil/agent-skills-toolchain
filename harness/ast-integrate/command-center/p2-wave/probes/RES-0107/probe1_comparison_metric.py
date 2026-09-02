#!/usr/bin/env python3
"""Probe 1: named comparison metric + cited measurement or explicit downgrade."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402


def main() -> int:
    doc = C.load_doc()
    good = C.check_document(doc)
    cmp_errs = C.comparison_errors(doc)
    mutant = C.mutant_competitive_without_downgrade(doc)
    bad = C.comparison_errors(mutant)
    two_rails = []
    for claim in doc.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        two_rails.extend(C.two_rails_errors(claim, HERE / "captures"))

    payload = {
        "probe": "probe1-comparison-metric",
        "unit_id": "RES-0107",
        "comparison_metric_name": (doc.get("comparison_metric") or {}).get("name"),
        "cited_measurement": (doc.get("comparison_metric") or {}).get(
            "cited_measurement"
        ),
        "competitive_vs_embeddings_label": doc.get("competitive_vs_embeddings_label"),
        "competitive_claim_downgraded": doc.get("competitive_claim_downgraded"),
        "good_state": {"pass": good["pass"] and not cmp_errs, "errors": good["errors"] + cmp_errs},
        "mutant_without_downgrade": {
            "id": "NC-competitive-without-downgrade-or-baseline",
            "must_fail": True,
            "failed": bool(bad),
            "errors": bad,
        },
        "two_rails_errors": two_rails,
        "sentinel_present": C.SENTINEL in json.dumps(doc),
        "pass": False,
    }
    payload["pass"] = bool(
        payload["good_state"]["pass"]
        and payload["mutant_without_downgrade"]["failed"]
        and not two_rails
        and payload["sentinel_present"]
        and payload["competitive_claim_downgraded"] is True
        and payload["competitive_vs_embeddings_label"] == "DESIGN-PREFERENCE"
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not payload["pass"]:
        print("FAILED:RES-0107-probe1 comparison metric / downgrade / rails")
        return 1
    print(
        "SUCCESS:RES-0107-probe1 named SWE-bench Lite metric; 26.3% cited; "
        "competitive vs embeddings downgraded; mutant without downgrade fails"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
