"""IMP-0103 probe1: near-duplicate rejection, casing/length gates, live-keyword sweep.

Signal 1 (catalog): the gate rejects a near-duplicate tag (reverse-engineering vs
reverse_engineering) and accepts a genuinely new one. Signal 2: a sweep over the
CURRENT keyword set confirms every existing tag passes; if a live tag fails the
threshold is wrong and must be reported rather than enforced.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from tag_gate import (  # noqa: E402
    load_params,
    load_plugin_keywords,
    sweep_live_keywords,
    validate_free_tag,
)


def main() -> int:
    params = load_params()
    live = load_plugin_keywords()
    checks = {}

    checks["threshold_declared"] = (
        "similarity_threshold" in params and "similarity_metric" in params
    )
    threshold = float(params["similarity_threshold"])

    nd = validate_free_tag("reverse_engineering", live)
    checks["near_duplicate_rejected"] = (not nd.accepted) and nd.reason == "near-duplicate"
    checks["near_duplicate_names_nearest"] = nd.nearest == "reverse-engineering"

    cv = validate_free_tag("Reverse-Engineering", live)
    checks["casing_variant_is_already_present"] = (
        cv.accepted and cv.reason == "already-present" and cv.nearest_score == 1.0
    )

    ol = validate_free_tag("a" * 33, live)
    checks["over_length_rejected"] = (not ol.accepted) and ol.reason == "over-length"

    nw = validate_free_tag("sbom-attestation", live)
    checks["genuinely_new_accepted"] = nw.accepted and nw.reason == "new"
    checks["new_below_threshold"] = nw.nearest_score < threshold

    sweep = sweep_live_keywords()
    checks["sweep_all_accepted"] = bool(sweep["all_accepted"])
    checks["sweep_count_is_seven"] = int(sweep["count"]) == 7
    checks["sweep_not_threshold_wrong"] = sweep["threshold_wrong"] is False

    out = {
        "unit_id": "IMP-0103",
        "probe": "probe1-near-duplicate-and-keyword-sweep",
        "threshold": threshold,
        "threshold_declared": checks["threshold_declared"],
        "live_keywords": live,
        "near_duplicate": nd.as_dict(),
        "casing_variant": cv.as_dict(),
        "over_length": ol.as_dict(),
        "genuinely_new": nw.as_dict(),
        "sweep": {k: sweep[k] for k in ("all_accepted", "count", "enforcement", "threshold", "threshold_wrong")},
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0103-probe1 near-duplicate rejected; casing accepted; sweep of 7 live keywords accepted; threshold declared")
        return 0
    print("FAILED:IMP-0103-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
