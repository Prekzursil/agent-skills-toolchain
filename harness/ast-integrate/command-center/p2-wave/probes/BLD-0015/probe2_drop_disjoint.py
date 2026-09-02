#!/usr/bin/env python3
"""Probe 2: drop-one, protocol∩preset empty, md/json SET identity, max() is wrong."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import count as C  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0015.json"
DROP_ID = "bp.distill-logs"
FX_KEYS = (
    "blueprints",
    "flagship-blueprints",
    "workflow-candidates",
    "council-protocols",
    "editable-presets",
    "architectures",
    "unique-ideas",
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0015-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0015" not in json.dumps(doc):
        print("FAILED:BLD-0015-probe2 sentinel absent")
        return 1

    dest = C.write_fixtures()
    fx = C.measure_pair(dest / "library.json", dest / "library.md")
    j_drop, m_drop = C.drop_one(
        dest / "library.json",
        dest / "library.md",
        "blueprints",
        DROP_ID,
        dest / "drop-one",
    )
    fx_drop = C.measure_pair(j_drop, m_drop)
    drop_ok = (
        fx_drop["blueprints"]["measured_json"] == fx["blueprints"]["measured_json"] - 1
        and fx_drop["blueprints"]["measured_md"] == fx["blueprints"]["measured_md"] - 1
        and fx_drop["blueprints"]["sets_identical"]
    )

    disjoint = fx["disjoint"] == []
    sum_ok = fx["sum_protocols_presets"] == fx["h4_total"]
    max_wrong = fx["max_would_be"] != fx["h4_total"]
    overlap_path = C.plant_overlap(dest / "library.json", dest / "overlap")
    overlap_doc = C.extract_library_json(overlap_path)
    overlap = set(e["id"] for e in overlap_doc["protocols"]) & set(
        e["id"] for e in overlap_doc["presets"]
    )
    overlap_fires = len(overlap) > 0

    pair_ok = all(fx[k]["sets_identical"] for k in FX_KEYS)
    live = C.live_census()
    wu_ok = live["work_unit_sets_identical"]
    arch_ok = set(live["architecture_ids_json"]) == set(live["architecture_ids_text"])

    rec_dis = doc.get("disjointness") or {}
    rec_ok = rec_dis.get("empty") is True and rec_dis.get("sum_equals_h4") is True

    ok = all(
        [drop_ok, disjoint, sum_ok, max_wrong, overlap_fires, pair_ok, wu_ok, arch_ok, rec_ok]
    )
    result = {
        "probe": "probe2-drop-disjoint",
        "unit_id": "BLD-0015",
        "drop_id": DROP_ID,
        "before": fx["blueprints"]["measured_json"],
        "after": fx_drop["blueprints"]["measured_json"],
        "drop_by_1": drop_ok,
        "protocol_n": fx["protocol_n"],
        "preset_n": fx["preset_n"],
        "h4_total": fx["h4_total"],
        "intersection": fx["disjoint"],
        "disjoint": disjoint,
        "sum_equals_h4": sum_ok,
        "max_is_wrong": max_wrong,
        "overlap_plant_fired": overlap_fires,
        "md_json_sets_identical": pair_ok,
        "work_units_sets_identical": wu_ok,
        "architectures_sets_identical": arch_ok,
        "pass": ok,
    }
    print(json.dumps(result, sort_keys=True))
    print(
        f"drop {fx['blueprints']['measured_json']}->{fx_drop['blueprints']['measured_json']} "
        f"disjoint={disjoint} sum={fx['protocol_n']}+{fx['preset_n']}={fx['h4_total']} "
        f"max={fx['max_would_be']} overlap_fire={overlap_fires}"
    )
    if not ok:
        print("FAILED:BLD-0015-probe2 drop-one / disjointness / set-identity")
        return 1
    print("SUCCESS:BLD-0015-probe2 drop-one, disjointness, cross-extractor set identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
