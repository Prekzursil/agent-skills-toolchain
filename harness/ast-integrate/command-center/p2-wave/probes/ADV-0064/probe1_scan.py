#!/usr/bin/env python3
"""Probe 1: confusable scan of existing registry names vs the protected set.

Reads names from a live PackageIndex (seeded with this worktree's first-party
marketplace name plus the estate first-party name). Does not publish.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import confusable as C  # noqa: E402
import publish_path as P  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0064-probe1 {msg}")
    return 1


def main() -> int:
    world = P.seed_world()
    existing = P.names_on_disk(world.index)
    protected = P.protected_set()
    collisions = C.ranked_collisions(existing, protected)
    generated = C.generate_confusable(protected[0])
    homoglyph = C.generate_homoglyph(protected[0])
    distinct = P.DISTINCT_CONTROL
    gen_hits = C.ranked_collisions([generated], protected)
    glyph_hits = C.ranked_collisions([homoglyph], protected)
    distinct_hits = C.ranked_collisions([distinct], protected)
    mutant_hits = C.mutant_flags_distinct(distinct, protected)
    scan = P.source_scan()
    paths = P.live_module_paths()

    report = {
        "probe": "probe1-namespace-scan",
        "unit_id": "ADV-0064",
        "mechanism": "folded-levenshtein-plus-unicode-confusable-table",
        "index_path": str(world.index.path),
        "existing_names": existing,
        "protected_set": protected,
        "live_marketplace_pkg": P.LIVE_MARKETPLACE_PKG,
        "ranked_collisions": collisions,
        "collision_count": len(collisions),
        "generated_confusable": generated,
        "generated_hits": gen_hits,
        "homoglyph_confusable": homoglyph,
        "homoglyph_hits": glyph_hits,
        "distinct_control": distinct,
        "distinct_hits": distinct_hits,
        "mutant_distinct_hits": mutant_hits,
        "both_states": {
            "id": "NC-FALSE-POSITIVE-DISTINCT",
            "fired_on_bad_state": bool(mutant_hits),
            "silent_on_good_state": not bool(distinct_hits),
        },
        "source_scan": scan,
        "live_module_paths": paths,
        "first_party_metadata_present": False,
        "popularity_metric_present": False,
        "record_blob_is_live_marketplace_index": paths["record_blob"].replace(
            "\\", "/"
        ).endswith("tools/marketplace/index.py"),
    }
    print(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False))

    if set(existing) != set(protected):
        return fail(f"seed/index mismatch existing={existing} protected={protected}")
    if collisions:
        return fail(f"unexpected existing-name collision {collisions}")
    if not gen_hits:
        return fail(f"scanner missed generated confusable {generated}")
    if gen_hits[0]["folded_distance"] != 0:
        return fail(f"generated fold distance {gen_hits[0]}")
    if not glyph_hits:
        return fail(f"scanner missed homoglyph {homoglyph!r}")
    if distinct_hits:
        return fail(f"distinct control listed as confusable {distinct_hits}")
    if not mutant_hits:
        return fail("mutant scanner silent on distinct control")
    if scan["confusable_gate_present"]:
        return fail("unexpected confusable gate in index/payload source")
    if scan["name_grammar_test_present"]:
        return fail("test_name_grammar.py present; probe1 assumed it absent")
    if not report["record_blob_is_live_marketplace_index"]:
        return fail(f"imported record_blob from {paths['record_blob']}")
    if P.LIVE_MARKETPLACE_PKG not in existing:
        return fail("live marketplace PKG missing from seeded index")

    print(
        "existing_collisions=0 generated_hit="
        f"{generated} homoglyph_hit={homoglyph!r} distinct_silent={distinct} "
        f"mutant_fired={bool(mutant_hits)}"
    )
    print("SUCCESS:ADV-0064-probe1 namespace-scan folded-distance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
