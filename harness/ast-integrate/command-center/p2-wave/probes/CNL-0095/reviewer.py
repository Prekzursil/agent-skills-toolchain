"""Cross-check reviewer: re-runs both-states on fixtures, not on author prose."""
from __future__ import annotations

from typing import Any

import detector as D
import fixtures as F


def review() -> dict[str, Any]:
    bad = D.detect(F.planted_bad())
    good = D.detect(F.known_good())
    kp = D.detect(F.known_present())
    easy = D.detect(F.easy_met_quota())
    late = D.detect(F.round10_premature())
    ok = (
        bad["fired"] is True
        and good["fired"] is False
        and good["status"] == "SILENT"
        and kp["fired"] is True
        and easy["fired"] is False
        and late["fired"] is True
    )
    return {
        "reviewer_id": "CNL-0095-both-states-rerun",
        "independent": True,
        "both_states_rerun": True,
        "executed_both_states": True,
        "verdict": "PASS" if ok else "FAIL",
        "planted_bad_fired": bad["fired"],
        "known_good_fired": good["fired"],
        "known_present_fired": kp["fired"],
        "easy_fired": easy["fired"],
        "round10_premature_fired": late["fired"],
        "scope_not_agreement": True,
    }
