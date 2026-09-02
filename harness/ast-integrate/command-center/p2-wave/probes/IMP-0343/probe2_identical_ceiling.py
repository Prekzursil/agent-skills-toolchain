#!/usr/bin/env python3
"""Probe 2: identical briefs score at the top of the similarity range.

Independent of probe 1's distribution-separation path. Starts from
identical_ceiling / shared_phrase_census, not the author's summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402
from tools.council.antifail.independence import CEILING  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0343.json"
UNIT = "IMP-0343"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    ctrl = S.identical_control()
    print(json.dumps(ctrl, sort_keys=True))

    if not ctrl["all_token_at_ceiling"]:
        return fail("identical briefs did not all score at the ceiling")
    if any(abs(s - CEILING) > 1e-12 for s in ctrl["token_scores"]):
        return fail(f"token_scores {ctrl['token_scores']} not all {CEILING}")
    if ctrl["ceiling"] != CEILING:
        return fail(f"ceiling {ctrl['ceiling']} != {CEILING}")
    if ctrl["shared_phrase_count"] < 1:
        return fail("identical briefs produced an empty shared-phrase census")
    if ctrl["census_from_loader"] < 1:
        return fail("load_council census empty on identical briefs")
    needle = "halt after two silent rounds"
    if not any(needle in p for p in ctrl["shared_phrases_head"]):
        return fail(f"census missed copied phrase {needle!r}")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0343" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    measured = doc.get("measured") or {}
    if measured.get("identical_all_token_at_ceiling") is not True:
        return fail("receipt identical_all_token_at_ceiling drift")
    if measured.get("identical_ceiling") != CEILING:
        return fail("receipt identical_ceiling drift")

    print(
        f"all_token_at_ceiling={ctrl['all_token_at_ceiling']} "
        f"scores={ctrl['token_scores']} "
        f"shared_phrase_count={ctrl['shared_phrase_count']}"
    )
    print("SUCCESS:IMP-0343-probe2 identical briefs at ceiling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
