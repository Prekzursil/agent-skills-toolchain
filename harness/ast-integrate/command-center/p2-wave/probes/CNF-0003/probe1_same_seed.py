#!/usr/bin/env python3
"""Probe 1: same-seed redraw is byte-identical; every P0/P1 id is in the frame.

Also re-computes the infinite-population detection n from ln(1-c)/ln(1-p).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sampler as S  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0003-sampling-frame.json"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:CNF-0003-probe1 artifact absent")
        return 1
    art = json.loads(OUT.read_text(encoding="utf-8"))
    view = S.sampling_view(art)
    claims, source = S.resolve_population()
    seed = int(view.get("seed") or -1)
    if seed != S.SEED:
        print(f"FAILED:CNF-0003-probe1 seed {seed} != sampler.SEED {S.SEED}")
        return 1
    strata_rec = list(view.get("strata") or [])
    drawn = S.redraw_from_strata(strata_rec, seed)
    live_json = S.canonical_id_list(drawn)
    recorded = str(view.get("drawn_ids_canonical_json") or "")
    recorded_list = view.get("drawn_ids") or []
    recorded_json = S.canonical_id_list(list(recorded_list))
    attached = view.get("same_seed_reproduction") or {}
    attached_json = str(attached.get("canonical_json") or "")
    same = live_json == recorded == recorded_json == attached_json
    print(f"same_seed={seed} ids={len(drawn)} canonical_match={same}")
    if not same:
        print("FAILED:CNF-0003-probe1 same-seed list is not byte-identical")
        print(f"  live={live_json[:180]}")
        print(f"  art ={recorded[:180]}")
        return 1
    independent = S.concat_drawn(S.build_strata(claims, seed=seed))
    if S.canonical_id_list(independent) != live_json:
        print("FAILED:CNF-0003-probe1 independent resolve_population redraw drifted")
        return 1
    diff = S.p0_p1_set_difference(claims, drawn)
    print(
        f"census p0p1 registry={diff['registry_p0p1_count']} "
        f"missing={diff['registry_minus_frame']} extra={diff['frame_p0p1_minus_registry']}"
    )
    if not diff["registry_minus_frame_empty"] or not diff["frame_p0p1_minus_registry_empty"]:
        print("FAILED:CNF-0003-probe1 P0/P1 set-difference is non-empty")
        return 1
    art_diff = view.get("p0_p1_set_difference") or {}
    if art_diff.get("registry_minus_frame") != []:
        print("FAILED:CNF-0003-probe1 artifact census field is not empty")
        return 1
    live_ids = {c["id"] for c in claims}
    ungraded = list((view.get("population_source") or {}).get("live_ungraded_ids") or [])
    leaked = [cid for cid in ungraded if cid in live_ids or cid in drawn]
    if leaked:
        print(f"FAILED:CNF-0003-probe1 live ungraded ids leaked into the frame: {leaked}")
        return 1
    n_live = S.infinite_population_n()
    n_art = int((view.get("sample_size") or {}).get("infinite_population_n") or -1)
    ratio = math.log(1.0 - S.CONFIDENCE) / math.log(1.0 - S.P_CLASS_ERROR)
    n_hand = int(math.ceil(ratio - 1e-12))
    p21 = 1.0 - (0.9**21)
    p22 = 1.0 - (0.9**22)
    arith_ok = n_live == n_art == n_hand == 22 and p21 < 0.90 <= p22
    print(f"interval n={n_live} n_art={n_art} n_hand={n_hand} p21={p21:.6f} p22={p22:.6f} ok={arith_ok}")
    if not arith_ok:
        print("FAILED:CNF-0003-probe1 interval arithmetic disagreement")
        return 1
    live_rows = S.build_strata(claims, seed=seed)
    for row, live_row in zip(strata_rec, live_rows):
        if row.get("population") != live_row["population"] or row.get("draw") != live_row["draw"]:
            print(f"FAILED:CNF-0003-probe1 stratum {row.get('id')} population/draw drift")
            return 1
        if S.canonical_id_list(list(row.get("drawn_ids") or [])) != S.canonical_id_list(
            live_row["drawn_ids"]
        ):
            print(f"FAILED:CNF-0003-probe1 stratum {row.get('id')} drawn_ids drift")
            return 1
    sampled = [row for row in live_rows if row["mode"] == "sample"]
    if not sampled:
        print("FAILED:CNF-0003-probe1 no sampled stratum")
        return 1
    print(
        f"population kind={source.get('kind')} live_present={source.get('live_registry_present')} "
        f"ungraded={len(ungraded)}"
    )
    print("SUCCESS:CNF-0003-probe1 same-seed reproduction and P0/P1 census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
