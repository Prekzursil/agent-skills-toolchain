#!/usr/bin/env python3
"""Probe 1: before-state control task selects its known-correct capability.

Re-runs the live router on the fixture index. Does not trust the artifact's
answers object for the control verdict. Then confirms the confirmation
artifact recorded the same control hit and the catalog completion sentinel.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import selection as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0055-router-selection-diff.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def catalog_sentinel() -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "CNF-0055":
            return str(unit.get("completion_sentinel") or "")
    return ""


def main() -> int:
    measured = S.measure()
    print(
        "control_ok="
        + str(measured["control_ok"])
        + " top1="
        + str((measured["control_topk"] or [{}])[0].get("capability_id"))
        + " expected="
        + str(measured["control_expected"])
        + " labelled_top1="
        + str(measured["labelled_top1_hits"])
        + "/"
        + str(measured["labelled_count"])
        + " nofit_ok="
        + str(measured["nofit_ok"])
        + " discriminating="
        + str(measured["corpus_discriminating"])
    )
    if not measured["control_ok"]:
        print("FAILED:CNF-0055-probe1 before-state control missed known-correct capability")
        return 1
    if not measured["corpus_discriminating"]:
        print("FAILED:CNF-0055-probe1 corpus is not discriminating")
        return 1
    if not measured["nofit_ok"]:
        print("FAILED:CNF-0055-probe1 T-NOFIT was not a terminal no-fit")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0055-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0055":
        print("FAILED:CNF-0055-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0055-probe1 self-declared", doc.get("state"))
        return 1
    sentinel = catalog_sentinel()
    if not sentinel or sentinel not in text:
        print("FAILED:CNF-0055-probe1 catalog completion_sentinel absent")
        return 1
    ctrl = S.artifact_field(doc, "control") or {}
    if ctrl.get("before_selected_known_correct") is not True:
        print("FAILED:CNF-0055-probe1 artifact control flag false")
        return 1
    if ctrl.get("expected_capability") != measured["control_expected"]:
        print("FAILED:CNF-0055-probe1 artifact control expected drifted")
        return 1
    if not ctrl.get("corpus_discriminating"):
        print("FAILED:CNF-0055-probe1 artifact corpus_discriminating false")
        return 1
    print("SUCCESS:CNF-0055-probe1 before-state control selected known-correct capability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
