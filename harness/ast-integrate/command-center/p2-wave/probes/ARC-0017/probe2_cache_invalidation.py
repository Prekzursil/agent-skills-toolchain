#!/usr/bin/env python3
"""Probe 2: stale-cache-masks-a-fixed-package is unreachable under the design.

Catalog tests_required[1]: walk the class through the design and show it is
unreachable. Negative control: a name-keyed cache mutant MUST make it reachable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import machine as M  # noqa: E402

DESIGN = REPO / "command-center/phase3/A3/DESIGN.json"


def main() -> int:
    design_walk = M.walk_stale_cache_masks_fix(digest_in_key=True)
    mutant_walk = M.walk_stale_cache_masks_fix(digest_in_key=False)
    print(
        "design digest_in_key=True "
        f"in_place_rejected={design_walk['in_place_rejected']} "
        f"masked={design_walk['masked']} "
        f"reachable={design_walk['class_reachable']} "
        f"fetched_after_miss={design_walk['fetched_after_miss']}"
    )
    print(
        "mutant digest_in_key=False "
        f"in_place_rejected={mutant_walk['in_place_rejected']} "
        f"masked={mutant_walk['masked']} "
        f"reachable={mutant_walk['class_reachable']}"
    )
    if not design_walk["in_place_rejected"]:
        print("FAILED:ARC-0017-probe2 in-place version mutation was accepted")
        return 1
    if design_walk["masked"] or design_walk["class_reachable"]:
        print("FAILED:ARC-0017-probe2 class still reachable under digest key")
        return 1
    if design_walk["activated_digest"] != design_walk["d_good"]:
        print("FAILED:ARC-0017-probe2 design did not activate D_good")
        return 1
    if not design_walk["fetched_after_miss"]:
        print("FAILED:ARC-0017-probe2 expected cache MISS then fetch of D_good")
        return 1
    if not mutant_walk["masked"] or not mutant_walk["class_reachable"]:
        print("FAILED:ARC-0017-probe2 mutant did not mask the fix — both-states fail")
        return 1
    if mutant_walk["activated_digest"] != mutant_walk["d_bad"]:
        print("FAILED:ARC-0017-probe2 mutant should have activated D_bad")
        return 1
    if design_walk["d_bad"] == design_walk["d_good"]:
        print("FAILED:ARC-0017-probe2 payloads were not distinct")
        return 1

    if not DESIGN.is_file():
        print("FAILED:ARC-0017-probe2 DESIGN.json absent")
        return 1
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    rule = design.get("cache_invalidation") or {}
    if rule.get("stale_cache_masks_fixed_package") != "UNREACHABLE":
        print(
            "FAILED:ARC-0017-probe2 DESIGN did not claim UNREACHABLE "
            f"got={rule.get('stale_cache_masks_fixed_package')}"
        )
        return 1
    if rule.get("activation_lookup_key") != "digest":
        print("FAILED:ARC-0017-probe2 DESIGN activation_lookup_key is not digest")
        return 1
    if rule.get("name_keyed_lookup_activates") is not False:
        print("FAILED:ARC-0017-probe2 DESIGN must forbid name-keyed activation")
        return 1
    walk = rule.get("walk") or {}
    if walk.get("d_bad") != design_walk["d_bad"] or walk.get("d_good") != design_walk["d_good"]:
        print("FAILED:ARC-0017-probe2 DESIGN walk digests drifted from live")
        return 1
    if "SUCCESS:ARC-0017" not in json.dumps(design):
        print("FAILED:ARC-0017-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0017-probe2 stale-cache-masks-fix unreachable (mutant reachable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
