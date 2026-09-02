#!/usr/bin/env python3
"""Probe 1: unlicensed candidate never returns ADOPT (both-states with MIT twin).

The twins share id and a permissive marketing blurb. The only structural
difference is an actual MIT licence field + LICENSE text. If the stage reads
the blurb as a licence, both states collapse to ADOPT and this probe fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCOUT = REPO / "command-center" / "foundry" / "scout"
sys.path.insert(0, str(SCOUT))

from licence_stage import verify_one  # noqa: E402
from vocabulary import ADOPT_FAMILY  # noqa: E402

FIX = HERE / "fixtures" / "twins.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0210-probe1 {msg}")
    return 1


def main() -> int:
    doc = json.loads(FIX.read_text(encoding="utf-8"))
    target = doc["target_spdx"]
    unlicensed = doc["twins"]["unlicensed_permissive_blurb"]
    licensed = doc["twins"]["licensed_mit"]
    if unlicensed["id"] != licensed["id"]:
        return fail("twins must share id")
    if unlicensed["description"] != licensed["description"]:
        return fail("twins must share marketing blurb")
    if "licence" in unlicensed or "license" in unlicensed:
        return fail("unlicensed twin must omit licence fields")

    bad = verify_one(unlicensed, target_spdx=target)
    good = verify_one(licensed, target_spdx=target)

    if bad["disposition"] != "CLEAN-ROOM-REIMPLEMENT":
        return fail(f"unlicensed disposition={bad['disposition']!r} want CLEAN-ROOM-REIMPLEMENT")
    if bad["recommended"] or bad["adopt_family"] or bad["disposition"] in ADOPT_FAMILY:
        return fail(f"unlicensed was recommended/ADOPT: {bad}")
    if bad["reason"] != "LICENCE-UNKNOWN":
        return fail(f"unlicensed reason={bad['reason']!r}")
    if bad["spdx"] != "UNKNOWN":
        return fail(f"unlicensed spdx={bad['spdx']!r} (marketing coerced to SPDX)")

    if good["disposition"] != "ADOPT-AS-IS":
        return fail(f"MIT twin disposition={good['disposition']!r} want ADOPT-AS-IS")
    if not good["recommended"] or good["disposition"] not in ADOPT_FAMILY:
        return fail(f"MIT twin not recommended: {good}")
    if good["spdx"] != "MIT":
        return fail(f"MIT twin spdx={good['spdx']!r}")

    extra = doc["extra"]
    gpl = verify_one(extra["gpl_into_permissive_target"], target_spdx=target)
    mkt = verify_one(extra["marketing_only_permissive_word"], target_spdx=target)
    rider = verify_one(extra["mit_with_no_ml_rider"], target_spdx=target)
    for label, hit in (("gpl", gpl), ("marketing-word", mkt), ("rider", rider)):
        if hit["disposition"] in ADOPT_FAMILY or hit["recommended"]:
            return fail(f"{label} leaked into ADOPT: {hit}")
        if hit["disposition"] != "CLEAN-ROOM-REIMPLEMENT":
            return fail(f"{label} disposition={hit['disposition']!r}")

    out = {
        "probe": "probe1-both-states",
        "unit_id": "IMP-0210",
        "unlicensed": bad,
        "licensed_mit": good,
        "gpl": gpl,
        "marketing_word": mkt,
        "rider": rider,
        "same_id": bad["id"] == good["id"],
        "two_verdicts": [bad["disposition"], good["disposition"]],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "unlicensed="
        + bad["disposition"]
        + " mit="
        + good["disposition"]
        + " recommended_mit="
        + str(good["recommended"])
        + " recommended_unlicensed="
        + str(bad["recommended"])
    )
    print("SUCCESS:IMP-0210-probe1 unlicensed never ADOPT; MIT twin ADOPT-AS-IS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
