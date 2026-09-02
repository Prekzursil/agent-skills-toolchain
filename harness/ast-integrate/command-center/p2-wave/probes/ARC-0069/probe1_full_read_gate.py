#!/usr/bin/env python3
"""Probe 1: full-read gate, digest-only both-states, anchors derived from the file."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import FIXTURE_ENTRIES  # noqa: E402
from gate import admit, citations_from_scorecard, coverage, sections_present  # noqa: E402
from judges import digest_only_dimensions, score_entry  # noqa: E402

ART = REPO / "command-center/phase3/SCORECARDS.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0069-probe1 SCORECARDS.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    cards = [c for c in (doc.get("scorecards") or []) if c.get("standing")]
    if len(cards) < 9:
        print(f"FAILED:ARC-0069-probe1 standing_scorecards={len(cards)}")
        return 1
    failed = [c for c in cards if c.get("gate") != "PASS"]
    if failed:
        print(f"FAILED:ARC-0069-probe1 standing gate failures n={len(failed)}")
        return 1
    print(f"standing_pass={len(cards)} gate_fail_standing=0")

    dossier = copy.deepcopy(FIXTURE_ENTRIES["E-07"])
    present = sections_present(dossier)
    if "digest" in present:
        print("FAILED:ARC-0069-probe1 digest counted as a required section")
        return 1
    if "failure_modes" not in present or "design" not in present:
        print(f"FAILED:ARC-0069-probe1 derived sections missing {present}")
        return 1

    mutant = copy.deepcopy(dossier)
    mutant["unexpected_section"] = {"probe": "anchor-integrity"}
    before = set(sections_present(dossier))
    after = set(sections_present(mutant))
    if "unexpected_section" not in after or after != before | {"unexpected_section"}:
        print(f"FAILED:ARC-0069-probe1 anchors not derived from file after={after}")
        return 1
    print("anchor_integrity renamed_section_detected=True")

    full_card = {
        "dimensions": score_entry("J-A", dossier),
        "judge_id": "J-A",
        "entry_id": "E-07",
    }
    full = admit(dossier, full_card)
    print(f"full_read gate={full['gate']} ratio={full['coverage']['ratio']}")
    if full["gate"] != "PASS":
        print("FAILED:ARC-0069-probe1 full-read scorecard failed the gate")
        return 1

    digest_card = {
        "dimensions": digest_only_dimensions(dossier),
        "judge_id": "J-A",
        "entry_id": "E-07",
    }
    digest = admit(dossier, digest_card)
    cites = citations_from_scorecard(digest_card)
    cov = coverage(dossier, cites)
    print(f"digest_only gate={digest['gate']} ratio={cov['ratio']} cites={cites[:3]}")
    if digest["gate"] != "FAIL":
        print("FAILED:ARC-0069-probe1 digest-only scorecard was admitted")
        return 1

    print("SUCCESS:ARC-0069-probe1 full-read gate both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
