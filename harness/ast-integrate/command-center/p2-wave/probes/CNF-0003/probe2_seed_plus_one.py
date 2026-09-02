#!/usr/bin/env python3
"""Probe 2: seed+1 must produce a different id list than the recorded frame.

This is the control that the seed is actually consumed. A census-only frame
that ignored the seed would emit the same list at seed and seed+1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sampler as S  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0003-sampling-frame.json"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:CNF-0003-probe2 artifact absent")
        return 1
    art = json.loads(OUT.read_text(encoding="utf-8"))
    view = S.sampling_view(art)
    claims, _source = S.resolve_population()
    seed = int(view.get("seed") or -1)
    frame_json = S.canonical_id_list(list(view.get("drawn_ids") or []))
    strata_rec = list(view.get("strata") or [])
    live_same = S.canonical_id_list(S.redraw_from_strata(strata_rec, seed))
    live_alt = S.canonical_id_list(S.redraw_from_strata(strata_rec, seed + 1))
    attached = view.get("different_seed_control") or {}
    attached_json = str(attached.get("canonical_json") or "")
    attached_seed = int(attached.get("seed") or -1)
    differs = live_alt != frame_json and live_alt != live_same
    matches_attached = live_alt == attached_json
    print(
        f"seed={seed} seed_plus_one={seed + 1} attached_seed={attached_seed} "
        f"differs={differs} matches_attached={matches_attached}"
    )
    print(f"frame_ids={len(view.get('drawn_ids') or [])} alt_ids={len(json.loads(live_alt))}")
    if attached_seed != seed + 1:
        print("FAILED:CNF-0003-probe2 attached control seed is not seed+1")
        return 1
    if not differs:
        print("FAILED:CNF-0003-probe2 seed+1 list is not different; seed may be unused")
        print(f"  alt={live_alt[:180]}")
        return 1
    if not matches_attached:
        print("FAILED:CNF-0003-probe2 live seed+1 does not match attached control")
        print(f"  live={live_alt[:180]}")
        print(f"  att ={attached_json[:180]}")
        return 1
    if not attached.get("differs_from_frame") is True:
        print("FAILED:CNF-0003-probe2 artifact did not record differs_from_frame=true")
        return 1
    if live_same != frame_json:
        print("FAILED:CNF-0003-probe2 same-seed redraw drifted while testing seed+1")
        return 1
    independent_alt = S.canonical_id_list(S.concat_drawn(S.build_strata(claims, seed=seed + 1)))
    if independent_alt != live_alt:
        print("FAILED:CNF-0003-probe2 independent seed+1 redraw drifted from recorded populations")
        return 1
    print("SUCCESS:CNF-0003-probe2 seed+1 control produces a different list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
