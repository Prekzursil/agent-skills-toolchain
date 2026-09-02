#!/usr/bin/env python3
"""Probe 2: planted dropped stage fires; both-states + overclaim + false-positive controls.

Bad state: drop unique-capability stage `cite` from fusion.keep-all.
Good state: unmodified fusion.keep-all stays silent.
False-positive control: drop redundant `scout-dup` (same tokens as `scout`) stays silent.
Overclaim control: after dropping `cite`, a stale declared capability_vector that still
lists the lost tokens must not hide the loss.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from fusion.capability_loss import (  # noqa: E402
    FAILURE_CLASS,
    FAILURE_CLASS_ID,
    capability_vector,
    detect_capability_loss,
    index_workflows,
    load_library,
    plant_dropped_stage,
    resolve_sources,
)

LIB = HERE / "fixtures" / "library.json"
PLANT_FUSION = "fusion.keep-all"
PLANT_STAGE = "cite"
EXPECTED_LOST = frozenset({"cap.cite", "gate:citation.required"})


def _ok(name: str, cond: bool, detail: str = "") -> bool:
    print(f"{name}={cond}" + (f" {detail}" if detail else ""))
    return bool(cond)


def main() -> int:
    library = load_library(LIB)
    catalog = index_workflows(library)
    fusion = catalog[PLANT_FUSION]
    sources = resolve_sources(fusion, catalog)

    good = detect_capability_loss(fusion, sources)
    planted = plant_dropped_stage(fusion, PLANT_STAGE)
    bad = detect_capability_loss(planted, sources)

    independent_lost = (set().union(*(capability_vector(s) for s in sources))) - set(
        capability_vector(planted)
    )

    overclaim_fusion = dict(planted)
    overclaim_fusion["capability_vector"] = sorted(
        set(capability_vector(fusion)) | EXPECTED_LOST
    )
    overclaim = detect_capability_loss(overclaim_fusion, sources)

    redundant = catalog["fusion.redundant-scout"]
    redundant_sources = resolve_sources(redundant, catalog)
    redundant_drop = plant_dropped_stage(redundant, "scout-dup")
    redundant_rec = detect_capability_loss(redundant_drop, redundant_sources)

    checks = [
        (
            "good_silent",
            good["fired"] is False and good["set_difference_empty"] is True,
            f"lost={good['lost']}",
        ),
        (
            "bad_fires",
            bad["fired"] is True and bad["set_difference_empty"] is False,
            f"lost={bad['lost']}",
        ),
        (
            "named_failure_class",
            bad["failure_class"] == FAILURE_CLASS
            and bad["failure_class_id"] == FAILURE_CLASS_ID,
            f"class={bad['failure_class']!r} id={bad['failure_class_id']!r}",
        ),
        (
            "lost_tokens_named",
            EXPECTED_LOST <= set(bad["lost"]),
            f"lost={bad['lost']}",
        ),
        (
            "independent_set_diff_agrees",
            independent_lost == set(bad["lost"]) and EXPECTED_LOST <= independent_lost,
            f"independent={sorted(independent_lost)}",
        ),
        (
            "overclaim_declared_vector_cannot_hide_drop",
            overclaim["fired"] is True and EXPECTED_LOST <= set(overclaim["lost"]),
            f"lost={overclaim['lost']}",
        ),
        (
            "redundant_drop_silent",
            redundant_rec["fired"] is False and redundant_rec["lost"] == [],
            f"lost={redundant_rec['lost']}",
        ),
        (
            "both_states_discriminate",
            (not good["fired"]) and bad["fired"] and (good["lost"] != bad["lost"]),
            "",
        ),
    ]

    print(
        json.dumps(
            {
                "probe": "probe2-planted-loss",
                "unit_id": "IMP-0191",
                "plant": {"fusion": PLANT_FUSION, "dropped_stage": PLANT_STAGE},
                "good_fired": good["fired"],
                "bad_fired": bad["fired"],
                "bad_lost": bad["lost"],
                "failure_class": bad["failure_class"],
            },
            sort_keys=True,
        )
    )

    failed = False
    for name, cond, detail in checks:
        if not _ok(name, cond, detail):
            failed = True
    if failed:
        print("FAILED:IMP-0191-probe2 planted capability loss not detected cleanly")
        return 1
    print("SUCCESS:IMP-0191-probe2 planted dropped stage fires both-states control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
