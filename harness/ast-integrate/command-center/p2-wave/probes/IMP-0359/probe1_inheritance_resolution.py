#!/usr/bin/env python3
"""Named probe 1: single- and multi-level inheritance plus live propagation.

Falsifiable: mutating a base and re-resolving descendants updates every child
that did not override the mutated field. Copy-paste catalogs would not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.presets.inherit import (  # noqa: E402
    MEASURED_COUNT,
    InheritError,
    build_measured_72,
    descendants,
    find_safety_weakenings,
    mutate_and_reresolve,
    resolve,
    resolve_all,
)

MODULE = REPO / "tools" / "council" / "presets" / "inherit.py"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0359-probe1 {msg}")
    return 1


def mini_catalog() -> dict[str, dict]:
    return {
        "base": {
            "id": "base",
            "dials": {
                "evidence_standard": "primary-source",
                "anti_sycophancy": "enforced",
                "quorum": 4,
                "max_rounds": 8,
                "protocol": "deliberative",
            },
        },
        "child": {
            "id": "child",
            "extends": "base",
            "overrides": {"dials": {"max_rounds": 12, "label": "child"}},
        },
        "grand": {
            "id": "grand",
            "extends": "child",
            "overrides": {"dials": {"reviewer_count": 3, "label": "grand"}},
        },
        "sibling": {
            "id": "sibling",
            "extends": "base",
            "overrides": {"dials": {"quorum": 7}},
        },
    }


def main() -> int:
    if not MODULE.is_file() or MODULE.stat().st_size < 200:
        return fail("tools/council/presets/inherit.py missing")

    cat = mini_catalog()
    child = resolve("child", cat)
    if child["dials"]["quorum"] != 4:
        return fail(f"single-level did not inherit quorum: {child['dials']}")
    if child["dials"]["max_rounds"] != 12:
        return fail("single-level override of max_rounds lost")
    if child["dials"]["evidence_standard"] != "primary-source":
        return fail("single-level evidence_standard not inherited")
    if child["dials"]["anti_sycophancy"] != "enforced":
        return fail("single-level anti_sycophancy not inherited")
    if child.get("_trace") != ["base"]:
        return fail(f"child trace {child.get('_trace')}")

    grand = resolve("grand", cat)
    if grand["dials"]["quorum"] != 4:
        return fail("multi-level quorum not inherited from base")
    if grand["dials"]["max_rounds"] != 12:
        return fail("multi-level did not inherit child's max_rounds override")
    if grand["dials"]["reviewer_count"] != 3:
        return fail("grandchild override lost")
    if grand.get("_trace") != ["base", "child"]:
        return fail(f"grand trace {grand.get('_trace')}")

    try:
        resolve("missing", cat)
        return fail("missing parent did not raise")
    except InheritError:
        pass

    cyclic = {
        "a": {"id": "a", "extends": "b", "dials": {"quorum": 1}},
        "b": {"id": "b", "extends": "a", "dials": {"quorum": 2}},
    }
    try:
        resolve("a", cyclic)
        return fail("cycle did not raise")
    except InheritError as exc:
        if "cycle" not in str(exc):
            return fail(f"cycle error missing marker: {exc}")

    desc = descendants("base", cat)
    if set(desc) != {"child", "grand", "sibling"}:
        return fail(f"descendants of base = {desc}")

    before = resolve_all(cat)
    after = mutate_and_reresolve(cat, "base", {"dials": {"quorum": 99, "protocol": "mutated"}})
    if after["child"]["dials"]["quorum"] != 99:
        return fail("child did not inherit mutated quorum")
    if after["grand"]["dials"]["quorum"] != 99:
        return fail("grandchild did not inherit mutated quorum")
    if after["sibling"]["dials"]["quorum"] != 7:
        return fail("sibling override of quorum was clobbered by base mutation")
    if after["child"]["dials"]["protocol"] != "mutated":
        return fail("child did not inherit mutated protocol")
    if after["grand"]["dials"]["protocol"] != "mutated":
        return fail("grandchild did not inherit mutated protocol")
    if before["child"]["dials"]["quorum"] == after["child"]["dials"]["quorum"]:
        return fail("propagation produced identical child quorum — copy-paste, not inherit")
    if after["child"]["dials"]["max_rounds"] != 12:
        return fail("propagation dropped child's declared max_rounds")

    measured = build_measured_72()
    if len(measured) != MEASURED_COUNT:
        return fail(f"measured catalog {len(measured)} != {MEASURED_COUNT}")
    resolved_72 = resolve_all(measured)
    if len(resolved_72) != MEASURED_COUNT:
        return fail("resolve_all dropped presets")
    for pid, raw in measured.items():
        parent = raw.get("extends")
        if not parent:
            continue
        got = resolved_72[pid]
        parent_res = resolved_72[parent]
        if got["dials"]["quorum"] != parent_res["dials"]["quorum"] and "quorum" not in (
            (raw.get("overrides") or {}).get("dials") or {}
        ):
            return fail(f"{pid} quorum diverged from {parent} without an override")
        if parent not in (got.get("_trace") or []):
            return fail(f"{pid} trace missing parent {parent}")

    mutated_72 = mutate_and_reresolve(
        measured, "root.00", {"dials": {"protocol": "mutated-root-00"}}
    )
    touched = 0
    for pid, raw in measured.items():
        in_line = pid == "root.00" or "root.00" in (mutated_72[pid].get("_trace") or [])
        if in_line:
            if mutated_72[pid]["dials"]["protocol"] != "mutated-root-00":
                return fail(f"{pid} did not inherit root.00 protocol mutation")
            touched += 1
        else:
            if mutated_72[pid]["dials"].get("protocol") == "mutated-root-00":
                return fail(f"{pid} incorrectly inherited an unrelated base mutation")
    if touched < 2:
        return fail("root.00 mutation reached no descendants")

    weakenings = find_safety_weakenings(measured)
    if weakenings:
        return fail(
            "measured 72 produced safety weakenings: "
            + json.dumps([w.as_dict() for w in weakenings[:5]])
        )

    payload = {
        "pass": True,
        "probe": "probe1-inheritance-resolution",
        "unit_id": "IMP-0359",
        "single_level_inherited_quorum": child["dials"]["quorum"],
        "multi_level_trace": grand.get("_trace"),
        "propagation_child_quorum_before": before["child"]["dials"]["quorum"],
        "propagation_child_quorum_after": after["child"]["dials"]["quorum"],
        "sibling_override_held": after["sibling"]["dials"]["quorum"] == 7,
        "measured_count": MEASURED_COUNT,
        "measured_descendants_of_root00": touched - 1,
        "measured_weakenings": 0,
        "copy_paste_refuted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "single_level=ok multi_level=ok "
        f"propagation {before['child']['dials']['quorum']}->{after['child']['dials']['quorum']} "
        f"measured={MEASURED_COUNT} weakenings=0"
    )
    print("SUCCESS:IMP-0359-probe1 single and multi-level inheritance resolution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
