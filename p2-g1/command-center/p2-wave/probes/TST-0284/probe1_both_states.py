#!/usr/bin/env python3
"""TST-0284 probe 1: both-states control.

missing-field fixture REJECTED (the missing list names refuting_observation);
empty refuting_observation REJECTED; well-formed fixture ACCEPTED with no
over-blocking (no missing elements, no circular flag).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixtures import EMPTY_REFUTING, MISSING_REFUTING, WELL_FORMED  # noqa: E402
from validator import validate  # noqa: E402


def main() -> int:
    checks: dict[str, bool] = {}
    m = validate(MISSING_REFUTING)
    checks["missing_refuting_observation_rejected"] = m["accepted"] is False
    checks["missing_list_names_field"] = m["missing"] == ["refuting_observation"]
    e = validate(EMPTY_REFUTING)
    checks["empty_refuting_observation_rejected"] = e["accepted"] is False
    w = validate(WELL_FORMED)
    checks["well_formed_accepted"] = w["accepted"] is True
    checks["well_formed_no_overblock"] = (
        w["missing"] == [] and w["circular"] is None
    )
    out = {
        "probe": "probe1_both_states",
        "unit": "TST-0284",
        "control": "missing-field fixture REJECTED; well-formed fixture ACCEPTED",
        "results": {"missing": m, "empty_refuting": e, "well_formed": w},
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-both-states.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
