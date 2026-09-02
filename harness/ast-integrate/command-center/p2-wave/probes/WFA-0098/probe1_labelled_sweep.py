#!/usr/bin/env python3
"""Probe 1: labelled pair set + threshold sweep with both error rates.

Recomputes the sweep from the planted labelled set (evidence A) and
checks the artifact reports false-collapse AND false-split at the chosen
point. A single accuracy number is not enough.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibrate import calibrate  # noqa: E402
from labelled_pairs import labelled_pairs, score_live  # noqa: E402

UNIT = "WFA-0098"
ART = REPO / "command-center/wfa/WFA-0098-duplicate-threshold-calibration.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not object")
    if str(doc.get("unit_id")) != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:WFA-0098" not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    live_pairs = labelled_pairs()
    two_dir = [p for p in live_pairs if p["two_directional_divergence"]]
    print(f"labelled_pairs n={len(live_pairs)} two_dir={len(two_dir)}")
    if len(two_dir) < 1:
        return fail("two-directional-divergence absent from labelled set")
    for p in two_dir:
        if not p["unique_left"] or not p["unique_right"]:
            return fail(f"{p['pair_id']} not two-directional unique content")
        live = score_live(p)
        if abs(live - p["jaccard"]) > 1e-9:
            return fail(f"{p['pair_id']} stored jaccard != live")

    cal = calibrate()
    chosen = cal["chosen"]
    art_cal = doc.get("calibration") or {}
    art_chosen = art_cal.get("chosen") or {}
    for key in (
        "threshold",
        "false_collapse_rate",
        "false_split_rate",
        "false_collapse_count",
        "false_split_count",
    ):
        if key not in art_chosen:
            return fail(f"artifact chosen missing {key}")
        if art_chosen[key] != chosen[key]:
            return fail(f"artifact {key} {art_chosen[key]} != live {chosen[key]}")

    if "accuracy" in art_chosen and "false_collapse_rate" not in art_chosen:
        return fail("accuracy present without both error rates")
    if art_chosen["false_collapse_rate"] is None or art_chosen["false_split_rate"] is None:
        return fail("error rates null")
    sweep = art_cal.get("sweep") or []
    if len(sweep) < 10:
        return fail(f"sweep too short {len(sweep)}")
    for row in sweep:
        if "false_collapse_rate" not in row or "false_split_rate" not in row:
            return fail("sweep row missing both rates")
        if "accuracy" in row and "false_collapse_rate" not in row:
            return fail("sweep accuracy without false_collapse_rate")

    if int(art_cal.get("n_two_directional_divergence") or 0) != len(two_dir):
        return fail("artifact two-dir count mismatch")
    if chosen["two_dir_false_collapses"] != 0:
        return fail("chosen threshold collapses two-dir pairs")

    print(
        "chosen_t="
        + str(chosen["threshold"])
        + " false_collapse_rate="
        + str(chosen["false_collapse_rate"])
        + " false_split_rate="
        + str(chosen["false_split_rate"])
        + " two_dir_false_collapses="
        + str(chosen["two_dir_false_collapses"])
        + " sweep_n="
        + str(len(sweep))
    )
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-labelled-sweep",
                "unit_id": UNIT,
                "n_pairs": len(live_pairs),
                "n_two_dir": len(two_dir),
                "false_collapse_rate": chosen["false_collapse_rate"],
                "false_split_rate": chosen["false_split_rate"],
                "threshold": chosen["threshold"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0098-probe1 labelled sweep both error rates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
