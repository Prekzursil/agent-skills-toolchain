#!/usr/bin/env python3
"""Probe 2: live divergences are reported per direction, never as one number.

Re-runs the gate against existing command-center tooling and checks the
conformance artifact's direction object has the seven named counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gate as G  # noqa: E402
import surfaces as S  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0104.json"


def main() -> int:
    live = S.run_live()
    directions = live["directions"]
    try:
        G.assert_named_directions(directions)
    except AssertionError as exc:
        print(f"FAILED:ARC-0104-probe2 {exc}")
        return 1
    if live["verdict"] == "DETECTOR-FAILURE":
        print("FAILED:ARC-0104-probe2 live verdict DETECTOR-FAILURE")
        return 1
    if live["caption_sum"] < 1:
        print("FAILED:ARC-0104-probe2 live tree reported zero divergences")
        return 1
    nonzero = [k for k in G.DIRECTION_KEYS if directions[k]["count"] > 0]
    if len(nonzero) < 2:
        print(f"FAILED:ARC-0104-probe2 fewer than two live directions fired: {nonzero}")
        return 1
    if not live["detector_control"]["fired"]:
        print("FAILED:ARC-0104-probe2 detector control not fired on live run")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0104-probe2 conformance artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:ARC-0104" not in json.dumps(doc):
        print("FAILED:ARC-0104-probe2 sentinel absent")
        return 1
    art_dir = G.artifact_section(doc, "directions")
    try:
        G.assert_named_directions(art_dir)
    except AssertionError as exc:
        print(f"FAILED:ARC-0104-probe2 artifact {exc}")
        return 1
    for key in G.DIRECTION_KEYS:
        live_c = directions[key]["count"]
        art_c = art_dir[key]["count"]
        if live_c != art_c:
            print(f"FAILED:ARC-0104-probe2 {key} live={live_c} artifact={art_c}")
            return 1
        live_f = directions[key]["fields"]
        art_f = art_dir[key]["fields"]
        if live_f != art_f:
            print(f"FAILED:ARC-0104-probe2 {key} field list drift")
            return 1
    contracts = G.artifact_section(doc, "contracts") or []
    if len(contracts) < 4:
        print(f"FAILED:ARC-0104-probe2 expected 4 contracts, got {len(contracts)}")
        return 1
    for block in contracts:
        try:
            G.assert_named_directions(block.get("directions"))
        except AssertionError as exc:
            print(f"FAILED:ARC-0104-probe2 contract {block.get('id')} {exc}")
            return 1
    tree = G.artifact_section(doc, "tree_fails_today") or {}
    dominant = tree.get("dominant_direction") if isinstance(tree, dict) else None
    if dominant not in G.DIRECTION_KEYS:
        print("FAILED:ARC-0104-probe2 tree_fails_today missing named direction")
        return 1

    counts = {k: directions[k]["count"] for k in G.DIRECTION_KEYS}
    out = {
        "probe": "probe2-direction-reporting",
        "unit_id": "ARC-0104",
        "verdict": live["verdict"],
        "caption_sum": live["caption_sum"],
        "direction_counts": counts,
        "nonzero_directions": nonzero,
        "tree_fails_today": live["tree_fails_today"]["dominant_direction"],
        "never_a_single_number": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:ARC-0104-probe2 per-direction counts "
        + ",".join(f"{k}={v}" for k, v in counts.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
