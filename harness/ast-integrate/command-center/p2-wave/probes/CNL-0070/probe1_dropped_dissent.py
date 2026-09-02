#!/usr/bin/env python3
"""Probe 1: a synthesis omitting a recorded dissent must FAIL the check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import preservation as P  # noqa: E402

OUT = HERE / "probe1-dropped-dissent.raw.json"


def main() -> int:
    dropped = F.dropped_dissent()
    good = F.known_good()
    footnote = F.footnote_only()
    partial = F.partial_drop()
    planted = P.plant_drop(good, "D-ALPHA")

    dropped_r = P.check(dropped)
    planted_r = P.check(planted)
    footnote_r = P.check(footnote)
    partial_r = P.check(partial)
    good_r = P.check(good)

    doc = {
        "probe": "probe1-dropped-dissent",
        "unit_id": "CNL-0070",
        "dropped": dropped_r,
        "planted_from_good": planted_r,
        "footnote": footnote_r,
        "partial_drop": partial_r,
        "known_good_control": {
            "silent": good_r["silent"],
            "fired": good_r["fired"],
        },
        "pass": False,
    }
    ok = (
        dropped_r["fired"]
        and planted_r["fired"]
        and footnote_r["fired"]
        and partial_r["fired"]
        and good_r["silent"]
        and "D-ALPHA" in dropped_r["conservation"]["missing_ids"]
        and "D-ALPHA" in planted_r["conservation"]["missing_ids"]
        and "D-ALPHA" in footnote_r["footnote_ids"]
        and "D-BETA" in partial_r["conservation"]["missing_ids"]
        and "D-ALPHA" not in partial_r["conservation"]["missing_ids"]
    )
    doc["pass"] = bool(ok)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "dropped_fired="
        + str(dropped_r["fired"])
        + " planted_fired="
        + str(planted_r["fired"])
        + " footnote_fired="
        + str(footnote_r["fired"])
        + " partial_missing="
        + ",".join(partial_r["conservation"]["missing_ids"])
        + " good_silent="
        + str(good_r["silent"])
        + " missing_on_drop="
        + ",".join(dropped_r["conservation"]["missing_ids"])
    )
    if not ok:
        print("FAILED:CNL-0070-probe1 dropped-dissent check did not fail the omitting synthesis")
        return 1
    print("SUCCESS:CNL-0070-probe1 dropped-dissent synthesis fails the check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
