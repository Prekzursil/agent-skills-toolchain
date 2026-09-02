#!/usr/bin/env python3
"""Probe 2: two-rail evidence, non-adoptable control, overclaim mutants.

Mechanically different from probe 1: does not re-decode GitHub API envelopes.
Drops source_lineage / a rail / the named non-adoptable feature and requires
the checker to go red. Hub-and-block must not be recorded as a better fit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0027-probe2 artifact missing")
        return 1
    doc = C.load_art()
    errs = C.validate_two_rail(doc)
    m1 = C.mutant_source_lineage_accepted(doc)
    m2 = C.mutant_drop_rail_accepted(doc)
    m3 = C.mutant_drop_non_adoptable_accepted(doc)
    print(
        json.dumps(
            {
                "errors": errs,
                "mutant_source_lineage_accepted": m1,
                "mutant_drop_rail_accepted": m2,
                "mutant_drop_non_adoptable_accepted": m3,
                "fit": doc.get("hub_and_block_better_fit_than_plugin_package"),
                "non_adoptable": (doc.get("block_composition_summary") or {}).get(
                    "named_non_adoptable_feature"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if errs:
        print("FAILED:RES-0027-probe2 " + "; ".join(errs[:8]))
        return 1
    if m1:
        print("FAILED:RES-0027-probe2 mutant without source_lineage was accepted")
        return 1
    if m2:
        print("FAILED:RES-0027-probe2 mutant with one rail was accepted")
        return 1
    if m3:
        print("FAILED:RES-0027-probe2 mutant without non-adoptable feature was accepted")
        return 1
    print(
        "SUCCESS:RES-0027-probe2 two-rails non-adoptable="
        f"{C.NON_ADOPTABLE!r} mutants-rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
