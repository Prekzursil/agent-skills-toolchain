#!/usr/bin/env python3
"""Probe 2: publish a generated confusable through the real index path.

Mechanically different from probe 1: this packs a blob and calls
PackageIndex.record_blob, then re-reads index.json. A scan that finds
collisions is worthless if nothing prevents new ones.
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
    print(f"FAILED:ADV-0064-probe2 {msg}")
    return 1


def main() -> int:
    world = P.seed_world()
    protected = P.protected_set()
    before = P.names_on_disk(world.index)
    generated = C.generate_confusable(protected[0])
    homoglyph = C.generate_homoglyph(protected[0])
    distinct = P.DISTINCT_CONTROL

    hell = P.publish_name(world, generated)
    glyph = P.publish_name(world, homoglyph)
    control = P.publish_name(world, distinct)
    after = P.names_on_disk(world.index)

    post_hits = C.ranked_collisions(after, protected)
    control_hits = [h for h in post_hits if h["name"] == distinct]
    gen_in_hits = [h for h in post_hits if h["name"] == generated]
    glyph_in_hits = [h for h in post_hits if h["name"] == homoglyph]
    scan = P.source_scan()
    paths = P.live_module_paths()

    report = {
        "probe": "probe2-real-publish",
        "unit_id": "ADV-0064",
        "mechanism": "pack_package-plus-PackageIndex.record_blob",
        "index_path": str(world.index.path),
        "names_before": before,
        "names_after": after,
        "protected_set": protected,
        "generated_confusable": generated,
        "homoglyph_confusable": homoglyph,
        "distinct_control": distinct,
        "hell0_publish": hell,
        "homoglyph_publish": glyph,
        "control_publish": control,
        "publish_refused_confusable": bool(hell.get("refused")),
        "publish_refused_homoglyph": bool(glyph.get("refused")),
        "control_distinct_published": (
            not bool(control.get("refused")) and bool(control.get("index_present"))
        ),
        "post_publish_collisions": post_hits,
        "generated_in_confusable_list": gen_in_hits,
        "homoglyph_in_confusable_list": glyph_in_hits,
        "control_in_confusable_list": control_hits,
        "source_scan": scan,
        "live_module_paths": paths,
        "record_blob_is_live_marketplace_index": paths["record_blob"].replace(
            "\\", "/"
        ).endswith("tools/marketplace/index.py"),
    }
    print(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False))

    if generated in before:
        return fail("generated name was already in the seeded index")
    if distinct in before:
        return fail("distinct control was already in the seeded index")
    if hell.get("blob_identity_name") != generated and not hell.get("refused"):
        return fail("pack_package did not embed generated name")
    if not hell.get("index_present") and not hell.get("refused"):
        return fail("record_blob did not persist generated name")
    if hell.get("refused"):
        # Honest measurement still succeeds; control below still must publish.
        pass
    else:
        if generated not in after:
            return fail("generated name missing from on-disk index after publish")
        if not gen_in_hits:
            return fail("published confusable not in post-publish collision list")
    if glyph.get("refused"):
        pass
    else:
        if homoglyph not in after:
            return fail("homoglyph name missing from on-disk index after publish")
    if control.get("refused") or not control.get("index_present"):
        return fail(f"distinct control failed to publish {control}")
    if distinct not in after:
        return fail("distinct control missing from on-disk index")
    if control_hits:
        return fail(f"distinct control listed as confusable {control_hits}")
    if not report["record_blob_is_live_marketplace_index"]:
        return fail(f"imported record_blob from {paths['record_blob']}")
    if scan["confusable_gate_present"]:
        return fail("unexpected confusable gate in index/payload source")

    print(
        f"generated={generated} refused={hell.get('refused')} "
        f"index={hell.get('index_present')} control={distinct} "
        f"control_present={distinct in after} control_confusable={bool(control_hits)}"
    )
    print("SUCCESS:ADV-0064-probe2 real-publish record_blob")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
