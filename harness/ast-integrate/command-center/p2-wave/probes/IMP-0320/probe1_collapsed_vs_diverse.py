#!/usr/bin/env python3
"""Probe 1: collapsed FIRE, diverse SILENT; similarity distributions separated.

Detector-control order: known-present collapsed is scored BEFORE diverse
silence. A declared-role-label decoy must stay SILENT on collapsed (roles
differ; outputs do not).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import collapsed_council, diverse_council  # noqa: E402
from load import load_detector  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0320.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0320-probe1 {msg}")
    return 1


def main() -> int:
    D = load_detector()
    collapsed = collapsed_council()
    diverse = diverse_council()

    # Detector-control first: known-present pathology.
    bad = D.detect(collapsed)
    print("detector_control_first=True fixture=collapsed")
    print(
        json.dumps(
            {
                "id": collapsed["id"],
                "fired": bad["fired"],
                "status": bad["status"],
                "mean_pairwise_jaccard": bad["mean_pairwise_jaccard"],
                "mean_role_vocab_score": bad["mean_role_vocab_score"],
            }
        )
    )
    if not bad["fired"] or bad["status"] != "FIRE":
        return fail("collapsed council did not FIRE")
    print("detector_control_found_known_present=True")

    good = D.detect(diverse)
    print(
        json.dumps(
            {
                "id": diverse["id"],
                "fired": good["fired"],
                "status": good["status"],
                "mean_pairwise_jaccard": good["mean_pairwise_jaccard"],
                "mean_role_vocab_score": good["mean_role_vocab_score"],
            }
        )
    )
    if good["fired"] or good["status"] != "SILENT":
        return fail("diverse council was not SILENT")

    bad_vals = [p["jaccard"] for p in bad["pairwise"]]
    good_vals = [p["jaccard"] for p in good["pairwise"]]
    if min(bad_vals) <= max(good_vals):
        return fail(
            f"distributions overlap collapsed_min={min(bad_vals)} "
            f"diverse_max={max(good_vals)}"
        )
    plot = D.side_by_side_histograms(bad_vals, good_vals)
    print(plot)

    decoy = D.declared_role_decoy(collapsed)
    print(
        f"decoy_declared_roles status={decoy['status']} "
        f"unique={decoy['unique_roles']}"
    )
    if decoy["fired"]:
        return fail("declared-role decoy FIRE on distinct labels; that measures labels")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0320" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    print(
        json.dumps(
            {
                "probe": "probe1-collapsed-vs-diverse",
                "unit_id": "IMP-0320",
                "collapsed_fired": True,
                "diverse_fired": False,
                "collapsed_mean": bad["mean_pairwise_jaccard"],
                "diverse_mean": good["mean_pairwise_jaccard"],
                "separated": True,
                "decoy_silent_on_collapsed": True,
                "pass": True,
            }
        )
    )
    print("SUCCESS:IMP-0320-probe1 collapsed FIRE diverse SILENT distributions separated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
