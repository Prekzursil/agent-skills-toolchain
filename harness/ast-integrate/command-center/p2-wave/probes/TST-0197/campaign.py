"""Live campaign for TST-0197: plant, enumerate, dir-list, regression seed."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import dirlist as DL
import enumerator as E
import fixture as F
import naive as N

HERE = Path(__file__).resolve().parent


def run_campaign() -> dict[str, Any]:
    planted_h = F.plant_hostile(HERE)
    planted_o = F.plant_ordinary(HERE)
    hostile = Path(planted_h["root"])
    ordinary = Path(planted_o["root"])

    enum_h = E.enumerate_tree(hostile)
    enum_o = E.enumerate_tree(ordinary)
    list_h = DL.listdir_tree(hostile)
    list_o = DL.listdir_tree(ordinary)

    seed = E.ntpath_relpath_regression()
    posix = E.posix_relpath_on_named_nul(hostile / "NUL", hostile)
    naive_raise = N.naive_ntpath_walk_raising(hostile)
    naive_zero = N.naive_ntpath_walk_swallowed(hostile)

    reserved_expected = sorted(E.RESERVED_BASENAMES)
    reserved_found = sorted({Path(r).name.upper() for r in enum_h["reserved"]})

    known_present = enum_h["known_present_found"]
    counts_match = (
        enum_h["complete"]
        and list_h["complete"]
        and enum_h["count"] == list_h["count"]
        and enum_h["count"] == planted_h["planted_count"]
        and sorted(enum_h["rels"]) == sorted(list_h["rels"])
        and sorted(enum_h["rels"]) == planted_h["planted"]
    )
    reserved_reported = reserved_found == reserved_expected
    ordinary_silent = enum_o["reserved"] == [] and enum_o["known_present_found"]
    silent_zero = (
        naive_zero.get("swallowed") is True
        and naive_zero.get("count") == 0
        and planted_h["planted_count"] > 0
    )
    no_exception = enum_h["exception"] is None and enum_h["complete"] is True
    not_silent_zero = enum_h["count"] not in (0, None)

    passed = all(
        [
            known_present,
            counts_match,
            reserved_reported,
            ordinary_silent,
            silent_zero,
            no_exception,
            not_silent_zero,
            seed["nul_raises_valueerror"],
            seed["all_reserved_raise_valueerror"],
            posix["raises"] is False,
            naive_raise.get("raised") is not None,
        ]
    )
    return {
        "pass": passed,
        "planted_hostile": planted_h,
        "planted_ordinary": planted_o,
        "enumerator_hostile": enum_h,
        "enumerator_ordinary": enum_o,
        "dirlist_hostile": list_h,
        "dirlist_ordinary": list_o,
        "regression_seed": seed,
        "posix_relpath_nul": posix,
        "naive_raising": naive_raise,
        "naive_swallowed": naive_zero,
        "checks": {
            "known_present_found": known_present,
            "counts_match": counts_match,
            "reserved_reported": reserved_reported,
            "ordinary_tree_no_reserved": ordinary_silent,
            "naive_swallow_is_silent_zero": silent_zero,
            "enumerator_no_exception": no_exception,
            "enumerator_not_silent_zero": not_silent_zero,
            "ntpath_nul_valueerror": seed["nul_raises_valueerror"],
            "posix_relpath_does_not_raise": posix["raises"] is False,
            "naive_walk_raises": naive_raise.get("raised") is not None,
        },
    }
