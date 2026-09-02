#!/usr/bin/env python3
"""Probe 2: nearest sibling, Draft202012 schema, negative controls."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preset as P  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0108-probe2 {msg}")
    return 1


def main() -> int:
    catalog = P.load_sibling_catalog()
    libs = P.library_present()
    print(f"library_on_disk={any(libs.values())} reconstructed_siblings={len(catalog)}")
    if any(libs.values()):
        print("NOTE: original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json appeared; still using reconstructed fixture for this unit")

    family = P.family_presets()
    expected_nearest = {"C-IL-LIVE": "C-ER47", "C-IL-RETRO": "C-ER-CRT"}
    sibling_rows = []
    for preset in family:
        sib, dist, diffs = P.nearest_sibling(preset, catalog)
        row = {
            "preset_id": preset["id"],
            "nearest_sibling": sib["id"],
            "distance": dist,
            "diff_axes": diffs,
            "name_only": dist == 0,
        }
        sibling_rows.append(row)
        print(json.dumps(row, sort_keys=True))
        if dist < 1:
            return fail(f"{preset['id']} is a name-only clone of {sib['id']}")
        want = expected_nearest[preset["id"]]
        if sib["id"] != want:
            return fail(
                f"{preset['id']} nearest sibling is {sib['id']} not {want} "
                f"(distance={dist} diffs={diffs})"
            )
        if "clock" not in diffs and "floor_may_skip" not in diffs:
            return fail(f"{preset['id']} vs {sib['id']} missing clock/floor differential")

    affected = catalog + family
    err_counts = []
    for rec in affected:
        errs = P.schema_errors(rec)
        err_counts.append((rec["id"], len(errs)))
        if errs:
            print(f"schema {rec['id']} errors={len(errs)} sample={errs[0]}")
            return fail(f"{rec['id']} schema errors {len(errs)}")
    print(f"schema_valid_records={len(affected)} errors=0")

    invalid = copy.deepcopy(family[0])
    del invalid["id"]
    invalid_errs = P.schema_errors(invalid)
    print(
        json.dumps(
            {
                "negative_control": "deliberately-invalid record with id removed",
                "error_count": len(invalid_errs),
                "sample": invalid_errs[:3],
                "vacuous_if_zero": len(invalid_errs) == 0,
            },
            sort_keys=True,
        )
    )
    if len(invalid_errs) < 1:
        return fail("Draft202012Validator is vacuous; invalid record produced 0 errors")

    by_id = {p["id"]: p for p in catalog}
    er47 = by_id["C-ER47"]
    clone = P.name_only_clone(er47, "C-IL-LIVE-FAKE", "Live war room in name only")
    dup = P.mechanism_duplicate(clone, er47)
    print(
        f"name_clone_of={er47['id']} new_id={clone['id']} "
        f"distance={P.distance(clone, er47)} duplicate={dup}"
    )
    if not dup:
        return fail("name-only clone was not detected")
    good_vs_er47 = P.mechanism_duplicate(family[0], er47)
    print(f"live_vs_C-ER47_duplicate={good_vs_er47} distance={P.distance(family[0], er47)}")
    if good_vs_er47:
        return fail("C-IL-LIVE collapsed into C-ER47")

    silent = copy.deepcopy(family[0])
    silent["floor_policy"] = dict(silent["floor_policy"])
    silent["floor_policy"]["may_skip_minimum_deliberation"] = False
    override = P.reject_non_editable_override(family[0], silent)
    print(
        json.dumps(
            {
                "negative_control_non_editable": (
                    "preset that silently clears may_skip_minimum_deliberation"
                ),
                "rejected": override["rejected"],
                "violations": override["violations"],
                "what_the_check_does": (
                    "REJECTS a write to floor_policy.may_skip_minimum_deliberation "
                    "because that dial is not in editable_dials; the live skip is "
                    "a typed delta, not an owner-tunable"
                ),
            },
            sort_keys=True,
        )
    )
    if not override["rejected"]:
        return fail("silent non-editable override was accepted")

    print("SUCCESS:CNL-0108-probe2 sibling-differential schema negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
