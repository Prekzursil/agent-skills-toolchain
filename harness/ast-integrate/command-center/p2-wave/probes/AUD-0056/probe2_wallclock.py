#!/usr/bin/env python3
"""Named probe 2: external wall-clock per module, twice.

In-runner --durations omits collection and fixture setup attributed elsewhere.
Each module is invoked as its own pytest process so those costs are paid here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import profile as P  # noqa: E402

ART = REPO / P.OUT
SCHEMA = REPO / P.SCHEMA


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0056-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != "AUD-0056":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    if P.COMPLETION not in text:
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:AUD-0056-probe2 schema")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1

    rank_ctl = P.ranking_detector_control()
    if not rank_ctl["pass"]:
        print(json.dumps(rank_ctl, indent=2)[:2000])
        return fail("ranking detector control does not discriminate")

    modules, collect_raw, collect_code = P.collect_modules()
    if not modules:
        print(collect_raw[-2000:])
        return fail(f"no modules collected collect_exit={collect_code}")

    wall_a = [P.run_wall_module(m) for m in modules]
    wall_b = [P.run_wall_module(m) for m in modules]
    if any(row["wall_s"] <= 0.0 for row in wall_a + wall_b):
        return fail("a wall-clock sample was not live (<=0)")
    covers = any(row["wall_covers_call"] for row in wall_a + wall_b)
    if not covers:
        print(json.dumps(wall_a, indent=2)[:3000])
        return fail("no module had wall-clock covering in-runner call time")

    map_a = {row["module"]: row for row in wall_a}
    map_b = {row["module"]: row for row in wall_b}
    vals_a = [float(map_a[m]["wall_s"]) for m in modules]
    vals_b = [float(map_b[m]["wall_s"]) for m in modules]
    live_rank = P.ranking_stability(modules, vals_a, vals_b)
    art_rank = doc.get("ranking") or {}
    art_slowest = str(art_rank.get("slowest_module_wall") or "")
    live_slowest = str(live_rank.get("slowest_run_a") or "")
    if art_slowest != live_slowest:
        return fail(f"slowest drifted artifact={art_slowest} live={live_slowest}")

    claimed_stable = bool(art_rank.get("wall_stable"))
    if claimed_stable and not live_rank["stable"]:
        return fail("artifact claimed wall ranking stable; live rerun is not")
    if doc.get("baseline_usable") and not live_rank["stable"]:
        return fail("artifact claimed baseline_usable; live wall ranking unstable")

    named = [p for p in (doc.get("named_probes") or []) if p.get("id") == "probe2"]
    if not named:
        return fail("artifact missing probe2 verbatim")
    raw = str(named[0].get("raw_output") or "")
    if "wall" not in raw.lower() and "module" not in raw.lower():
        return fail("probe2 raw_output has no wall-clock measurement")

    art_modules = {row.get("module") for row in (doc.get("modules") or [])}
    if set(modules) - art_modules:
        return fail(f"live modules missing from artifact {sorted(set(modules) - art_modules)}")

    tax_positive = any(
        float(map_a[m]["collection_and_unattributed_s"]) > 0.0
        or float(map_b[m]["collection_and_unattributed_s"]) > 0.0
        for m in modules
    )
    report = {
        "probe": "probe2-wallclock",
        "unit_id": "AUD-0056",
        "pass": True,
        "module_count": len(modules),
        "live_ranking": live_rank,
        "artifact_slowest": art_slowest,
        "wall_covers_call": covers,
        "collection_tax_observed": tax_positive,
        "samples": [
            {
                "module": m,
                "wall_a_s": map_a[m]["wall_s"],
                "wall_b_s": map_b[m]["wall_s"],
                "call_a_s": map_a[m]["call_s"],
                "tax_a_s": map_a[m]["collection_and_unattributed_s"],
            }
            for m in modules
        ],
    }
    for row in wall_a:
        print(
            f"WALL-A {row['module']} wall_s={row['wall_s']} call_s={row['call_s']} "
            f"reported_s={row['reported_s']} tax_s={row['collection_and_unattributed_s']} "
            f"exit={row['exit_code']}"
        )
    for row in wall_b:
        print(
            f"WALL-B {row['module']} wall_s={row['wall_s']} call_s={row['call_s']} "
            f"reported_s={row['reported_s']} tax_s={row['collection_and_unattributed_s']} "
            f"exit={row['exit_code']}"
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    print("SUCCESS:AUD-0056-probe2 live per-module wall-clock recorded twice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
