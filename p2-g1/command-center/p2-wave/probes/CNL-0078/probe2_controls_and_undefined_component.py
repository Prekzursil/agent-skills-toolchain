#!/usr/bin/env python3
"""Named probe 2 (CNL-0078): both-states control + the undefined component census.

The SILENT fixture must replay non-firing with the SAME inline parser (the
expression is not a fire-only tautology), and the spec's central answer - the
completeness component not defined anywhere - must be named, explained, and
backed by a live census whose identifier mentions still resolve on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from probe1_stopping_expression_replay import replay  # noqa: E402

def _catalog_artifact() -> Path:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in cat.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return REPO / str(u.get("output_path") or "").replace(chr(92), "/")
    raise RuntimeError(f"{UNIT} absent from catalog")


UNIT = "CNL-0078"
ART = _catalog_artifact()


def main() -> int:
    if not ART.is_file():
        print(f"FAILED:{UNIT}-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    runs = doc.get("fixture_runs") or {}
    silent = runs.get("silent_incomplete") or {}
    if not silent:
        print(f"FAILED:{UNIT}-probe2 silent_incomplete fixture absent")
        return 1
    replay_silent = replay(
        str(doc.get("verbatim_expression") or ""),
        silent,
    )
    if replay_silent:
        print(f"FAILED:{UNIT}-probe2 silent fixture replays as firing - not a both-states control")
        return 1
    if str(silent.get("verdict") or "").upper() != "SILENT" or silent.get("fired") is not False:
        print(f"FAILED:{UNIT}-probe2 recorded silent verdict mismatch")
        return 1

    answer = doc.get("answer") or {}
    undefined_component = str(answer.get("undefined_component") or "")
    if undefined_component != "coverage_domain_identity":
        print(f"FAILED:{UNIT}-probe2 undefined component not the coverage identity: {undefined_component!r}")
        return 1
    if not str(answer.get("undefined_component_detail") or "").strip():
        print(f"FAILED:{UNIT}-probe2 undefined component detail empty")
        return 1

    census = answer.get("live_census") or {}
    mentions = census.get("identifier_mentions") or []
    if not mentions:
        print(f"FAILED:{UNIT}-probe2 identifier-mention census empty")
        return 1
    missing = [
        m.get("path")
        for m in mentions[:5]
        if not (REPO / str(m.get("path") or "")).is_file()
    ]
    if missing:
        print(f"FAILED:{UNIT}-probe2 census mention paths missing on disk: {missing}")
        return 1
    outside = census.get("completeness_score_hits_outside_catalog_and_this_unit")
    if not isinstance(outside, list):
        print("FAILED:CNL-0078-probe2 outside-hits census absent")
        return 1

    negative = doc.get("negative_control") or doc.get("negative_controls")
    if not negative:
        print(f"FAILED:{UNIT}-probe2 negative control absent")
        return 1

    row = {
        "unit_id": UNIT,
        "probe": "probe2-controls-and-undefined-component",
        "replayed_silent": replay_silent,
        "recorded_verdict": silent.get("verdict"),
        "both_states_hold": True,
        "undefined_component": undefined_component,
        "census_mentions_checked_on_disk": min(5, len(mentions)),
        "outside_hits_present": True,
        "negative_control_present": True,
    }
    print(json.dumps(row, indent=1))
    print(f"SUCCESS:{UNIT}-probe2 both-states control and undefined-component census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
