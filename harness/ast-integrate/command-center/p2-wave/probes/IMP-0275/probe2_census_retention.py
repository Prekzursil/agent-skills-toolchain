"""Named probe 2 (independent reviewer): census retention and tally rule.

Starts from the invariants, not the author's summary:

1. Artifact census before vs after eviction — prior votes and ideas retained.
2. Vote tally recomputed with R-EVICT-RETAIN and compared to the recorded tally.
3. Negative control: drop the evicted member's ideas and assert the census FAILS.

Catalog tests:
  * unit: eviction triggers and quorum recomputation (covered in probe1;
    this probe re-checks contribution reachability after eviction)
  * negative control: drop the evicted member's ideas and assert the census FAILS
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.replace import (  # noqa: E402
    RULE_ID,
    census_retention_check,
    compute_tally,
    contribution_census,
    evict,
    make_run,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0275-probe2 {msg}")
    return 1


def main() -> int:
    before = make_run()
    before_census = contribution_census(before)
    closed_yes_before = before["tally"]["closed_rounds"]["1"]["counts"]["yes"]
    live_yes_before = before["tally"]["open_round"]["counts"]["yes"]

    after = evict(before, "dave", replacement={"id": "evan"})
    after_census = contribution_census(after)
    retention = census_retention_check(before_census, after_census)
    if not retention["ok"]:
        return fail(f"honest eviction lost contributions: {retention}")
    if after_census["orphan_ids"]:
        return fail(f"orphans after eviction: {after_census['orphan_ids']}")
    dave_ids = set(before_census["by_author"]["dave"])
    if dave_ids != {"v-r1-dave", "i-r1-dave", "v-r2-dave"}:
        return fail(f"unexpected dave census {dave_ids}")
    if set(after_census["by_author"]["dave"]) != dave_ids:
        return fail("dave contributions not reachable after eviction")
    if after_census["by_author"].get("evan"):
        return fail("replacement inherited dave's contributions")

    recorded = after["tally"]
    recomputed = compute_tally(after)
    if recorded != recomputed:
        return fail("recorded tally diverges from independent R-EVICT-RETAIN recompute")
    if recorded["rule_id"] != RULE_ID:
        return fail(f"missing tally rule {recorded.get('rule_id')}")
    if recorded["closed_rounds"]["1"]["counts"]["yes"] != closed_yes_before:
        return fail("closed-round tally dropped the evicted vote")
    if "dave" not in recorded["closed_rounds"]["1"]["includes_evicted"]:
        return fail("closed-round tally hid the evicted author")
    live_authors = {e["author_id"] for e in recorded["open_round"]["included"]}
    excluded = {e["author_id"] for e in recorded["open_round"]["excluded_evicted"]}
    if "dave" in live_authors or "dave" not in excluded:
        return fail("open-round live tally did not exclude the evicted seat")
    if recorded["open_round"]["counts"]["yes"] != live_yes_before - 1:
        return fail("live tally did not drop the evicted open-round vote")

    dropped = copy.deepcopy(after)
    dropped["contributions"] = [
        c
        for c in dropped["contributions"]
        if not (c["author_id"] == "dave" and c["kind"] == "idea")
    ]
    negative = census_retention_check(before_census, contribution_census(dropped))
    if negative["ok"] or "i-r1-dave" not in negative["missing"]:
        return fail(f"negative control silent after dropping ideas: {negative}")

    remapped = copy.deepcopy(after)
    for item in remapped["contributions"]:
        if item["id"] == "i-r1-dave":
            item["author_id"] = "evan"
    remap_check = census_retention_check(before_census, contribution_census(remapped))
    if remap_check["ok"] or "i-r1-dave" not in remap_check["remapped"]:
        return fail(f"author remap not detected: {remap_check}")

    payload = {
        "census_retained": True,
        "closed_yes_unchanged": True,
        "negative_control_fired": True,
        "orphan_ids": after_census["orphan_ids"],
        "pass": True,
        "probe": "probe2-census-retention",
        "remap_detected": True,
        "tally_matches_rule": True,
        "unit_id": "IMP-0275",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "census_retained=True tally_matches=True "
        "negative_control_fired=True remap_detected=True"
    )
    print("SUCCESS:IMP-0275-probe2 census retention and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
