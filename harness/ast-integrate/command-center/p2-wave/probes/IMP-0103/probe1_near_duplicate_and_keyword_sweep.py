#!/usr/bin/env python3
"""Named probe 1: near-duplicate reject, genuinely-new accept, live keyword sweep.

Signal 1 is the gate decision on reverse_engineering vs the live reverse-engineering
keyword (must refuse). Signal 2 is a sweep of the CURRENT plugin.json keyword set
(every live tag must pass; a failure is a wrong threshold, reported not enforced).
Both-states control: sbom-attestation is accepted as new in the same run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from tag_gate import (  # noqa: E402
    compact,
    load_plugin_keywords,
    normalize,
    sweep_live_keywords,
    validate_free_tag,
)


def main() -> int:
    keywords = load_plugin_keywords(REPO)
    if len(keywords) != 7:
        print(json.dumps({"keywords": keywords, "count": len(keywords)}))
        print(f"FAILED:IMP-0103-probe1 live keyword count={len(keywords)} want=7")
        return 1
    live_norm = {normalize(k) for k in keywords}
    if "reverse-engineering" not in live_norm:
        print("FAILED:IMP-0103-probe1 reverse-engineering missing from live keywords")
        return 1

    near = validate_free_tag("reverse_engineering", keywords)
    fresh = validate_free_tag("sbom-attestation", keywords)
    sweep = sweep_live_keywords(keywords)

    result = {
        "probe": "probe1-near-duplicate-and-keyword-sweep",
        "unit_id": "IMP-0103",
        "live_keywords": keywords,
        "near_duplicate": near.as_dict(),
        "genuinely_new": fresh.as_dict(),
        "keyword_sweep": {
            "all_accepted": sweep["all_accepted"],
            "count": sweep["count"],
            "enforcement": sweep["enforcement"],
            "failures": sweep["failures"],
            "threshold": sweep["threshold"],
            "threshold_wrong": sweep["threshold_wrong"],
        },
        "compact_equal": compact("reverse_engineering") == compact("reverse-engineering"),
        "pass": False,
    }

    if near.accepted or near.reason != "near-duplicate":
        print(json.dumps(result, indent=2, sort_keys=True))
        print("FAILED:IMP-0103-probe1 near-duplicate was not refused")
        return 1
    if not fresh.accepted or fresh.reason != "new":
        print(json.dumps(result, indent=2, sort_keys=True))
        print("FAILED:IMP-0103-probe1 genuinely new tag was not accepted")
        return 1
    if sweep["threshold_wrong"]:
        print(json.dumps(result, indent=2, sort_keys=True))
        print(
            "FAILED:IMP-0103-probe1 live keyword failed the gate; "
            "threshold is wrong and must be reported rather than enforced"
        )
        return 1
    if not sweep["all_accepted"] or sweep["enforcement"] != "enforce":
        print(json.dumps(result, indent=2, sort_keys=True))
        print("FAILED:IMP-0103-probe1 keyword sweep did not accept the live set")
        return 1

    result["pass"] = True
    print(json.dumps(result, indent=2, sort_keys=True))
    print(
        f"near_dup_rejected={not near.accepted} new_accepted={fresh.accepted} "
        f"live_keywords_ok={sweep['all_accepted']} n={sweep['count']}"
    )
    print(
        "SUCCESS:IMP-0103-probe1 near-duplicate refused, new tag accepted, "
        "live keywords pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
