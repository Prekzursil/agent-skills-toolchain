#!/usr/bin/env python3
"""Probe 2: anchors derived from dossier bytes; reviewer reproduces coverage.

A renamed section must fail a stale citation list. The same list against a
frozen hand-list still PASSes — that is the silent-pass defect of hand-listing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402

ART = REPO / "command-center/phase3/FULL-READ-GATE.json"
MUTATED = HERE / "fixtures" / "_mutated-dossier.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0068-probe2 {msg}")
    return 1


def main() -> int:
    if not G.FIXTURE_DOSSIER.is_file():
        return fail("fixture-dossier-absent")
    from_file = G.extract_anchors_from_path(G.FIXTURE_DOSSIER)
    from_obj = G.extract_anchors(G.load_json(G.FIXTURE_DOSSIER))
    print(f"anchors_from_file={from_file}")
    if from_file != from_obj:
        return fail("path-vs-object-anchor-drift")
    if len(from_file) < 2:
        return fail("too-few-derived-sections")

    trial = G.integrity_trial_from_file(G.FIXTURE_DOSSIER, MUTATED)
    print(
        "rename {0}->{1} stale={2} fresh={3} hand_list={4} silent_pass={5}".format(
            trial["old_name"],
            trial["new_name"],
            trial["stale_from_file"]["verdict"],
            trial["fresh_from_file"]["verdict"],
            trial["hand_list_frozen_from_original_file"]["verdict"],
            trial["hand_list_frozen_from_original_file"]["verdict"] == "PASS"
            and trial["stale_from_file"]["verdict"] == "FAIL",
        )
    )
    if not trial["ok"]:
        return fail("integrity-trial-failed")
    if trial["old_name"] in trial["anchors_after_from_file"]:
        return fail("old-name-still-derived-after-rename")
    if trial["new_name"] not in trial["anchors_after_from_file"]:
        return fail("new-name-not-derived-from-mutated-file")
    if trial["stale_from_file"]["verdict"] != "FAIL":
        return fail("stale-citations-silently-passed-derived-gate")
    if trial["fresh_from_file"]["verdict"] != "PASS":
        return fail("file-derived-citations-did-not-pass")
    if trial["hand_list_frozen_from_original_file"]["verdict"] != "PASS":
        return fail("hand-list-control-did-not-pass-stale-names")

    sampled = G.admit_paths(G.FIXTURE_FULL, G.FIXTURE_DOSSIER)
    cited = sampled["coverage"]["cited_distinct"]
    present = sampled["coverage"]["sections_present"]
    fraction = sampled["coverage"]["coverage_fraction"]
    print(f"reviewer_sample {fraction} verdict={sampled['verdict']}")
    if sampled["verdict"] != "PASS":
        return fail("sampled-full-scorecard-failed")
    if fraction != f"{cited}/{present}":
        return fail("fraction-mismatch")

    if not ART.is_file():
        return fail("FULL-READ-GATE.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    sample = doc.get("reviewer_sample") or {}
    if int(sample.get("cited_distinct") or -1) != cited:
        return fail(f"reviewer-cited-drift artifact={sample.get('cited_distinct')} live={cited}")
    if int(sample.get("sections_present") or -1) != present:
        return fail("reviewer-present-drift")
    if sample.get("coverage_fraction") != fraction:
        return fail("reviewer-fraction-drift")
    integrity = doc.get("anchor_integrity") or {}
    if integrity.get("old_name") != trial["old_name"]:
        return fail("artifact-rename-old-drift")
    if integrity.get("new_name") != trial["new_name"]:
        return fail("artifact-rename-new-drift")
    if integrity.get("stale_verdict") != "FAIL" or integrity.get("fresh_verdict") != "PASS":
        return fail("artifact-integrity-verdict-drift")
    if integrity.get("hand_list_would_silently_pass") is not True:
        return fail("artifact-did-not-record-hand-list-silent-pass")
    if "SUCCESS:ARC-0068" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    print("anchor_integrity=True reviewer_reproduced=True")
    print("SUCCESS:ARC-0068-probe2 anchor-integrity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
