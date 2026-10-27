#!/usr/bin/env python3
"""Build the TST-0284 probe scripts (keeps long dict-literal code out of my
direct-write path, which has a measured corruption failure mode)."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent / "command-center" / "p2-wave" / "probes" / "TST-0284"

P1 = '''#!/usr/bin/env python3
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
        json.dumps(out, indent=1, sort_keys=True) + "\\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P2 = '''#!/usr/bin/env python3
"""TST-0284 probe 2: circular refutations rejected + the program harvest.

Unobservable-in-principle (omniscient/infinite), omniscient, and
equals-claim refuting observations are all rejected as circular. The three
program impossibility records (reconstructed verbatim from the receipt
harvest rows) each score accepted=False with the receipt exact
missing-field lists. The three declared CNF/RES harvest paths are live on
this tree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import (  # noqa: E402
    CIRCULAR_UNOBSERVABLE,
    EQUALS_CLAIM,
    OMNISCIENT,
    PROGRAM_RECORDS,
)
from validator import validate  # noqa: E402


def main() -> int:
    checks: dict[str, bool] = {}
    cu = validate(CIRCULAR_UNOBSERVABLE)
    checks["circular_unobservable_rejected"] = cu["accepted"] is False
    checks["circular_reason_unobservable"] = bool(cu["circular"]) and (
        "unobservable" in cu["circular"]
    )
    om = validate(OMNISCIENT)
    checks["omniscient_rejected"] = om["accepted"] is False
    eq = validate(EQUALS_CLAIM)
    checks["equals_claim_rejected_as_circular"] = eq["accepted"] is False
    harvest_ok = True
    scored = []
    for rec in PROGRAM_RECORDS:
        v = validate(rec)
        ok = v["missing"] == rec["want_missing"] and (
            v["accepted"] == rec["want_accepted"]
        )
        harvest_ok = harvest_ok and ok
        scored.append(
            {
                "id": rec["id"],
                "accepted": v["accepted"],
                "missing": v["missing"],
                "matches_receipt_row": ok,
            }
        )
    checks["program_harvest_scores_match_receipt"] = harvest_ok
    cnf = REPO / "command-center" / "confirmation"
    res = REPO / "command-center" / "research" / "evidence-quality"
    declared = [
        cnf / "CNF-0026-impossibility-records.json",
        cnf / "CNF-0098-macos-reachability.json",
        res / "RES-0149-proof-of-impossibility-record-schema.json",
    ]
    live = [p.is_file() and p.stat().st_size > 0 for p in declared]
    checks["declared_harvest_paths_live"] = all(live)
    out = {
        "probe": "probe2_circular_and_harvest",
        "unit": "TST-0284",
        "circular_results": {
            "unobservable": cu,
            "omniscient": om,
            "equals_claim": eq,
        },
        "program_harvest": scored,
        "declared_paths_live": {
            str(p.relative_to(REPO)): ok for p, ok in zip(declared, live)
        },
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-circular-harvest.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    LANE.mkdir(parents=True, exist_ok=True)
    (LANE / "probe1_both_states.py").write_text(P1.replace("\\\\n", "\\n"), encoding="utf-8")
    (LANE / "probe2_circular_and_harvest.py").write_text(P2.replace("\\\\n", "\\n"), encoding="utf-8")
    print("built probe1/probe2 for TST-0284")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
