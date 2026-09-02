#!/usr/bin/env python3
"""Named probe 2 (negative control): inheritance weakening of evidence standard.

Both states: a good child that keeps or raises the base evidence standard is
silent; a child that weakens evidence_standard via inheritance makes the
check FIRE. A parent-wins merge that clobbers a child's stronger declaration
is the silent-weaken case and also fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.presets.inherit import (  # noqa: E402
    check_weakening,
    declared_overlay,
    find_safety_weakenings,
    resolve,
    resolve_all,
    resolve_strict,
    InheritError,
)

MODULE = REPO / "tools" / "council" / "presets" / "inherit.py"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0359-probe2 {msg}")
    return 1


def catalog_good() -> dict[str, dict]:
    return {
        "base": {
            "id": "base",
            "dials": {
                "evidence_standard": "primary-source",
                "anti_sycophancy": "enforced",
                "quorum": 4,
            },
        },
        "child": {
            "id": "child",
            "extends": "base",
            "overrides": {"dials": {"max_rounds": 9}},
        },
        "raised": {
            "id": "raised",
            "extends": "base",
            "overrides": {"dials": {"evidence_standard": "adversarial-replication"}},
        },
    }


def catalog_weak() -> dict[str, dict]:
    cat = catalog_good()
    cat["weak"] = {
        "id": "weak",
        "extends": "base",
        "overrides": {"dials": {"evidence_standard": "anecdote"}},
    }
    return cat


def catalog_anti_weak() -> dict[str, dict]:
    return {
        "base": {
            "id": "base",
            "dials": {
                "evidence_standard": "primary-source",
                "anti_sycophancy": "enforced",
            },
        },
        "weak_anti": {
            "id": "weak_anti",
            "extends": "base",
            "overrides": {"dials": {"anti_sycophancy": "off"}},
        },
    }


def catalog_declared_stronger() -> dict[str, dict]:
    return {
        "base": {
            "id": "base",
            "dials": {
                "evidence_standard": "citation",
                "anti_sycophancy": "advisory",
            },
        },
        "child": {
            "id": "child",
            "extends": "base",
            "dials": {
                "evidence_standard": "adversarial-replication",
                "anti_sycophancy": "enforced",
            },
        },
    }


def main() -> int:
    if not MODULE.is_file() or MODULE.stat().st_size < 200:
        return fail("tools/council/presets/inherit.py missing")

    good = catalog_good()
    silent = find_safety_weakenings(good)
    if silent:
        return fail(
            "good catalog fired: " + json.dumps([w.as_dict() for w in silent])
        )

    weak = catalog_weak()
    fired = find_safety_weakenings(weak)
    evidence_hits = [
        w for w in fired if w.field == "evidence_standard" and w.child_id == "weak"
    ]
    if not evidence_hits:
        return fail("weakening a child's evidence_standard via inheritance did not FIRE")
    hit = evidence_hits[0]
    if hit.child_rank >= hit.base_rank:
        return fail("finding did not record a rank regression")
    if str(hit.child_value) != "anecdote" or str(hit.base_value) != "primary-source":
        return fail(f"unexpected values {hit.as_dict()}")

    resolved_weak = resolve("weak", weak)
    if resolved_weak["dials"]["evidence_standard"] != "anecdote":
        return fail("resolve hid the weakening instead of producing it for the check")
    if resolved_weak["dials"]["anti_sycophancy"] != "enforced":
        return fail("weak child lost inherited anti_sycophancy")

    try:
        resolve_strict("weak", weak)
        return fail("resolve_strict accepted a weakened child")
    except InheritError:
        pass
    strict_ok = resolve_strict("child", good)
    if strict_ok["dials"]["evidence_standard"] != "primary-source":
        return fail("resolve_strict altered a non-weak child")

    anti = catalog_anti_weak()
    anti_hits = [
        w
        for w in find_safety_weakenings(anti)
        if w.field == "anti_sycophancy" and w.child_id == "weak_anti"
    ]
    if not anti_hits:
        return fail("anti-sycophancy weakening did not FIRE")

    clobber_cat = catalog_declared_stronger()
    honest = find_safety_weakenings(clobber_cat, parent_wins=False)
    if honest:
        return fail("child-wins merge fired on a strengthening child")
    clobbered = find_safety_weakenings(clobber_cat, parent_wins=True)
    silent_hits = [w for w in clobbered if w.kind == "silent-clobber-of-declared"]
    if not silent_hits:
        return fail("parent-wins merge did not FIRE silent clobber of declared evidence")
    clobber_resolved = resolve("child", clobber_cat, parent_wins=True)
    if clobber_resolved["dials"]["evidence_standard"] != "citation":
        return fail("parent-wins control did not actually clobber evidence_standard")

    child_res = resolve("child", good)
    base_res = resolve("base", good)
    both_silent = check_weakening(child_res, base_res, declared=declared_overlay(good["child"]))
    if both_silent:
        return fail("check_weakening fired on the good pair")

    payload = {
        "pass": True,
        "probe": "probe2-weaken-evidence",
        "unit_id": "IMP-0359",
        "good_state_silent": True,
        "evidence_weakening_fired": True,
        "anti_sycophancy_weakening_fired": True,
        "silent_clobber_fired": True,
        "resolve_strict_refused_weak": True,
        "finding": hit.as_dict(),
        "reviewer_starts_from_tests": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "good_silent=True evidence_fire=True anti_fire=True "
        "clobber_fire=True strict_refused_weak=True"
    )
    print("SUCCESS:IMP-0359-probe2 weaken child's evidence standard via inheritance FIRES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
