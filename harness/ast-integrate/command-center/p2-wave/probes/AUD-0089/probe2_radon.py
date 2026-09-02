#!/usr/bin/env python3
"""Probe 2: radon 6.0.1 over the same set; record ranking agreement or disagreement."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = str(HERE / "vendor") + os.pathsep + os.environ.get("PYTHONPATH", "")

import lib  # noqa: E402


def main() -> int:
    _liz_ver, rad_ver = lib.ensure_vendor()
    files = lib.discover_python()
    liz_rows = lib.lizard_functions(files)
    rad_rows = lib.radon_functions(files)
    comparison = lib.ranking_comparison(liz_rows, rad_rows)
    control = lib.fixture_control()
    other_langs = lib.other_language_census()
    payload = {
        "ccn_threshold": lib.CCN_THRESHOLD,
        "comparison": comparison,
        "control": control,
        "file_count": len(files),
        "histogram_radon": lib.histogram(rad_rows),
        "other_languages": other_langs,
        "over_ccn_15": lib.over_threshold(rad_rows),
        "pinned_radon": lib.PINNED_RADON,
        "probe": "probe2-radon",
        "radon_function_count": len(rad_rows),
        "radon_version": rad_ver,
        "same_file_set_as_lizard": True,
        "unit_id": "AUD-0089",
    }
    lib.dump(HERE / "probe2-radon.json", payload)
    print(json.dumps(
        {
            "agree_on_top_function": comparison["agree_on_top_function"],
            "control_fired": control["fired_on_bad_state"],
            "control_silent": control["silent_on_good_state"],
            "file_count": len(files),
            "headline_most_complex": comparison["headline_most_complex"],
            "lizard_only_over_15": comparison["lizard_only_over_15"],
            "lizard_over_15_count": comparison["lizard_over_15_count"],
            "other_languages": other_langs,
            "radon_only_over_15": comparison["radon_only_over_15"],
            "radon_over_15_count": comparison["radon_over_15_count"],
            "radon_version": rad_ver,
            "reason": comparison["reason"],
        },
        indent=2,
        sort_keys=True,
    ))
    if rad_ver != lib.PINNED_RADON:
        print("FAILED:AUD-0089-probe2 radon version mismatch")
        return 1
    if not files or not rad_rows or not liz_rows:
        print("FAILED:AUD-0089-probe2 empty analyzer report")
        return 1
    if not control["fired_on_bad_state"] or not control["silent_on_good_state"]:
        print("FAILED:AUD-0089-probe2 planted CCN control did not discriminate")
        return 1
    if other_langs:
        print(
            "FAILED:AUD-0089-probe2 non-python sources present without a second analyzer"
        )
        return 1
    print(
        f"SUCCESS:AUD-0089-probe2 radon {rad_ver} same-set ranking "
        f"agree={comparison['agree_on_top_function']} "
        f"over15 lizard={comparison['lizard_over_15_count']} "
        f"radon={comparison['radon_over_15_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
