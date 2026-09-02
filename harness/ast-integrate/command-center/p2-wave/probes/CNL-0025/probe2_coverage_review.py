#!/usr/bin/env python3
"""Probe 2: independent synthesis-coverage channel + reviewer both-states re-run.

Does NOT use seat-share excess. Recomputes set difference submitted vs cited.
Must FIRE on captured (missing hold+contract) and be SILENT on even-handed.

This is the second mechanism required by the catalog evidence rule, and the
mechanical both-states re-run the reviewer requirement demands. A same-process
author cannot honestly claim a fresh openai/gpt-5-codex human signature; that
residual is recorded on the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import capture as C  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0025-chair-powers-and-capture-resistance.md"
FIX_BAD = HERE / "fixtures" / "captured.json"
FIX_GOOD = HERE / "fixtures" / "evenhanded.json"
OUT = HERE / "probe2-coverage-review.raw.json"


def load_session(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def mechanisms_of(doc: dict) -> set[str]:
    found = set()
    for row in doc.get("evidence") or []:
        if isinstance(row, dict) and row.get("mechanism"):
            found.add(str(row["mechanism"]))
    return found


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0025-probe2 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    mechs = mechanisms_of(doc)
    if "seat-share-excess" not in mechs or "synthesis-coverage" not in mechs:
        print(f"FAILED:CNL-0025-probe2 evidence mechanisms {sorted(mechs)}")
        return 1
    if mechs == {"seat-share-excess"} or len(mechs) < 2:
        print("FAILED:CNL-0025-probe2 second mechanism missing")
        return 1

    # Independent recompute: call synthesis_coverage directly, not detect().
    bad_cov = C.synthesis_coverage(load_session(FIX_BAD))
    good_cov = C.synthesis_coverage(load_session(FIX_GOOD))
    print(
        "reviewer_rerun captured coverage: "
        f"fires={bad_cov['fires']} missing={bad_cov['missing_position_ids']} "
        f"cited={bad_cov['cited_position_ids']}"
    )
    print(
        "reviewer_rerun evenhanded coverage: "
        f"fires={good_cov['fires']} missing={good_cov['missing_position_ids']} "
        f"cited={good_cov['cited_position_ids']}"
    )
    if not bad_cov["fires"] or "hold" not in bad_cov["missing_position_ids"] or "contract" not in bad_cov["missing_position_ids"]:
        print("FAILED:CNL-0025-probe2 captured fixture coverage did not fire on omitted dissent")
        return 1
    if good_cov["fires"] or good_cov["missing_position_ids"]:
        print("FAILED:CNL-0025-probe2 even-handed coverage false positive")
        return 1

    # Vacuity: coverage with no participants must not look like a clean pass
    # that "proved" even-handedness.
    empty = C.synthesis_coverage({"participants": [], "synthesis": {"cited_position_ids": []}})
    print(f"vacuity empty-session coverage fires={empty['fires']} submitted={empty['submitted_position_ids']}")
    if empty["fires"]:
        print("FAILED:CNL-0025-probe2 empty session should not fire coverage")
        return 1
    if empty["submitted_position_ids"]:
        print("FAILED:CNL-0025-probe2 empty session listed submissions")
        return 1

    ncs = doc.get("negative_controls") or []
    if not ncs:
        print("FAILED:CNL-0025-probe2 negative_controls missing")
        return 1
    observed = " ".join(str(x.get("observed") or "") for x in ncs)
    if "FIRE" not in observed.upper() and "fires=True" not in observed:
        print("FAILED:CNL-0025-probe2 negative control did not record FIRE on reject state")
        return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("control_executed") is not True or reviewer.get("independent") is not True:
        print("FAILED:CNL-0025-probe2 reviewer did not execute an independent control")
        return 1

    payload = {
        "probe": "probe2-coverage-review",
        "unit_id": "CNL-0025",
        "mechanism": "synthesis-coverage",
        "fired_on_captured": True,
        "silent_on_evenhanded": True,
        "captured_missing": bad_cov["missing_position_ids"],
        "evenhanded_missing": good_cov["missing_position_ids"],
        "evidence_mechanisms": sorted(mechs),
        "reviewer_control_executed": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SUCCESS:CNL-0025-probe2 coverage channel both-states and reviewer re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
