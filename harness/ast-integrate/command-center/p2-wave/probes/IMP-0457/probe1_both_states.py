#!/usr/bin/env python3
"""Probe 1: under PR-ONLY condition 13 is N/A; under canary it is REQUIRED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import stopping_predicate as SP  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0457.json"
SENTINEL = "SENTINEL:IMP-0457:STOPPING-RULE-MODE-AWARE"


def main() -> int:
    both = SP.both_states()
    pr = SP.evaluate_all("PR-ONLY")
    canary = SP.evaluate_all("PRIVATE-CANARY")
    print(
        json.dumps(
            {
                "probe": "probe1-both-states-release-mode",
                "unit_id": "IMP-0457",
                "both_states": both["both_states"],
                "pr_only_c13_applicability": both["pr_only"]["c13_applicability"],
                "pr_only_c13_verdict": both["pr_only"]["c13_verdict"],
                "pr_only_na_count": both["pr_only"]["na_count"],
                "canary_c13_applicability": both["private_canary"]["c13_applicability"],
                "canary_c13_verdict": both["private_canary"]["c13_verdict"],
                "canary_na_count": both["private_canary"]["na_count"],
                "marketplace_c13_applicability": both["public_marketplace"][
                    "c13_applicability"
                ],
                "pr_only_valid": pr["valid"],
                "canary_valid": canary["valid"],
                "condition_count": pr["condition_count"],
            },
            sort_keys=True,
        )
    )
    if not both["both_states"]:
        print("FAILED:IMP-0457-probe1 both-states condition 13")
        return 1
    if both["pr_only"]["c13_applicability"] != "NOT-APPLICABLE":
        print("FAILED:IMP-0457-probe1 PR-ONLY must mark condition 13 N/A")
        return 1
    if both["private_canary"]["c13_applicability"] != "REQUIRED":
        print("FAILED:IMP-0457-probe1 canary must mark condition 13 REQUIRED")
        return 1
    if both["private_canary"]["c13_verdict"] == "NOT-APPLICABLE":
        print("FAILED:IMP-0457-probe1 canary condition 13 must not be N/A")
        return 1
    if both["pr_only"]["na_count"] != 1:
        print("FAILED:IMP-0457-probe1 expected exactly one N/A under PR-ONLY")
        return 1
    if both["private_canary"]["na_count"] != 0:
        print("FAILED:IMP-0457-probe1 canary must have zero N/A")
        return 1
    if pr["condition_count"] != 21 or canary["condition_count"] != 21:
        print("FAILED:IMP-0457-probe1 expected 21 conditions")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0457-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0457-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0457-probe1 self-declared", doc.get("state"))
        return 1
    rows = doc.get("conditions") or []
    if len(rows) != 21:
        print("FAILED:IMP-0457-probe1 receipt row count", len(rows))
        return 1
    c13 = next((r for r in rows if int(r.get("id") or 0) == 13), None)
    if not c13 or c13.get("verdict") != "NOT-APPLICABLE":
        print("FAILED:IMP-0457-probe1 receipt condition 13 not N/A")
        return 1
    if not str(c13.get("owner_visible_justification") or "").strip():
        print("FAILED:IMP-0457-probe1 receipt N/A lacks justification")
        return 1
    if str(doc.get("binding_release_mode") or "") != "PR-ONLY":
        print("FAILED:IMP-0457-probe1 binding mode not PR-ONLY")
        return 1
    print(
        "SUCCESS:IMP-0457-probe1 PR-ONLY N/A; canary REQUIRED; "
        "justification recorded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
