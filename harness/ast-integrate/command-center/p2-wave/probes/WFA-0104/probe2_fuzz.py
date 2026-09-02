#!/usr/bin/env python3
"""Probe 2: independent fuzz + both-states plants (signal B).

Fuzz generates well-typed inputs with a PRNG and shuffled key insertion —
it does not walk typed_universe. Every generated input must hit exactly one
branch; default must be taken at least once.

Plants (detector control): overlap → multiply-routed, hole → unrouted,
unfit → source-unfit, default-starved → default-unexercised. The good twin
must stay silent. A detector that is quiet on both plant and twin is inert.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_fusion.conditional_hybrid import FusionRefused  # noqa: E402
import scenario as S  # noqa: E402
from hybrid_op import (  # noqa: E402
    FUZZ_N,
    FUZZ_SEED,
    analyze_fitness,
    count_routing,
    emit_fusion_result,
    fuzz_routing,
)

ART = REPO / "command-center/wfa/WFA-0104-fusion-conditional-hybrid.json"
UNIT = "WFA-0104"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    good = S.good_spec()
    try:
        analyze_fitness(good)
    except FusionRefused as exc:
        return fail(f"good twin fitness refused: {exc}")
    fuzz_rep, fuzz_envs = fuzz_routing(good)
    if fuzz_rep.unrouted:
        return fail(f"fuzz unrouted={fuzz_rep.unrouted[:3]}")
    if fuzz_rep.multiply:
        return fail(f"fuzz multiply={fuzz_rep.multiply[:3]}")
    if fuzz_rep.default_taken < 1:
        return fail("fuzz never exercised default")
    if len(fuzz_envs) != FUZZ_N:
        return fail(f"fuzz n={len(fuzz_envs)} want {FUZZ_N}")
    try:
        emit_fusion_result(good)
    except FusionRefused as exc:
        return fail(f"good twin emit refused: {exc}")

    rows = []

    overlap = S.plant_overlap()
    orep, _ = fuzz_routing(overlap, n=300, seed=FUZZ_SEED + 1)
    if not orep.multiply:
        return fail("plant overlap: detector silent (no multiply-routed)")
    try:
        emit_fusion_result(overlap)
        return fail("plant overlap: emit accepted multiply-routed spec")
    except FusionRefused as exc:
        if exc.code != "fusion.conditional_hybrid.multiply-routed":
            return fail(f"plant overlap: refuse code {exc.code}")
        rows.append(
            {
                "plant": "overlap",
                "expect": "multiply-routed",
                "fired": True,
                "code": exc.code,
                "multiply": len(orep.multiply),
            }
        )

    hole = S.plant_hole()
    hrep = count_routing(hole, fuzz_envs)
    if not hrep.unrouted:
        return fail("plant hole: detector silent (no unrouted)")
    try:
        emit_fusion_result(hole)
        return fail("plant hole: emit accepted a hole")
    except FusionRefused as exc:
        if exc.code not in {
            "fusion.conditional_hybrid.unrouted-inputs",
            "fusion.conditional_hybrid.default-missing",
        }:
            return fail(f"plant hole: refuse code {exc.code}")
        rows.append(
            {
                "plant": "hole",
                "expect": "unrouted",
                "fired": True,
                "code": exc.code,
                "unrouted": len(hrep.unrouted),
            }
        )

    unfit = S.plant_unfit()
    try:
        analyze_fitness(unfit)
        return fail("plant unfit: fitness silent")
    except FusionRefused as exc:
        if exc.code != "fusion.conditional_hybrid.source-unfit":
            return fail(f"plant unfit: refuse code {exc.code}")
        rows.append(
            {
                "plant": "unfit",
                "expect": "source-unfit",
                "fired": True,
                "code": exc.code,
            }
        )

    starved = S.plant_default_starved()
    srep, _ = fuzz_routing(starved, n=300, seed=FUZZ_SEED + 2)
    if srep.default_taken != 0:
        return fail(f"plant default-starved: default_taken={srep.default_taken}")
    try:
        emit_fusion_result(starved)
        return fail("plant default-starved: emit accepted unexercised default")
    except FusionRefused as exc:
        if exc.code != "fusion.conditional_hybrid.default-unexercised":
            return fail(f"plant default-starved: refuse code {exc.code}")
        rows.append(
            {
                "plant": "default-starved",
                "expect": "default-unexercised",
                "fired": True,
                "code": exc.code,
                "default_taken": srep.default_taken,
            }
        )

    if len(rows) != 4:
        return fail(f"plants {len(rows)} want 4")

    if not ART.is_file():
        return fail("fusion artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    fz = doc.get("fuzz") or {}
    if fz.get("unrouted") != 0 or fz.get("multiply_routed") != 0:
        return fail(f"artifact fuzz {fz}")
    if fz.get("n") != FUZZ_N or fz.get("seed") != FUZZ_SEED:
        return fail(f"artifact fuzz n/seed {fz.get('n')} {fz.get('seed')}")
    if fz.get("default_taken") != fuzz_rep.default_taken:
        return fail(
            f"artifact fuzz default_taken={fz.get('default_taken')} "
            f"live={fuzz_rep.default_taken}"
        )
    if fz.get("taken") != fuzz_rep.taken:
        return fail(f"artifact fuzz taken drift {fz.get('taken')} vs {fuzz_rep.taken}")
    declared = {c["plant"] for c in doc.get("declared_negative_controls") or []}
    if declared != set(S.PLANTS):
        return fail(f"declared plants {declared}")

    out = {
        "probe": "probe2-fuzz",
        "unit_id": UNIT,
        "pass": True,
        "fuzz_n": FUZZ_N,
        "fuzz_seed": FUZZ_SEED,
        "unrouted": 0,
        "multiply_routed": 0,
        "default_taken": fuzz_rep.default_taken,
        "taken": fuzz_rep.taken,
        "good_emit_ok": True,
        "plants": rows,
        "plants_detected": len(rows),
        "plants_expected": 4,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"fuzz n={FUZZ_N} unrouted=0 multiply=0 default_taken={fuzz_rep.default_taken} "
        f"plants=4/4 good_silent=True"
    )
    print("SUCCESS:WFA-0104-probe2 fuzz zero unrouted/multiply and plants fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
