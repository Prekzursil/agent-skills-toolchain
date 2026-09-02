#!/usr/bin/env python3
"""Named probe 2: empty-but-present section must FAIL non-vacuity.

Independent reviewer path: starts from the complete twin and the vacuous
mutants, not from the census ranking. A presence-only checkbox is not a pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.completeness import (  # noqa: E402
    CHARTER_REQUIRED_OUTPUTS,
    check_artifact,
    complete_artifact,
    is_vacuous,
    vacuous_mutants,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0356-probe2 {msg}")
    return 1


def main() -> int:
    twin = complete_artifact("reviewer-twin")
    good = check_artifact(twin)
    if not good["pass"]:
        return fail(f"complete twin failed: {good}")

    fired = []
    silent_on_good = True
    for section in CHARTER_REQUIRED_OUTPUTS:
        for label, mutant in vacuous_mutants(twin, section):
            bad = check_artifact(mutant)
            if bad["pass"]:
                return fail(f"{section}/{label} empty-but-present passed")
            if section not in bad["missing"]:
                return fail(f"{section}/{label} not listed missing: {bad['missing']}")
            if not bad["present"].get(section):
                return fail(f"{section}/{label} treated as absent, not vacuous")
            if not bad["vacuous"].get(section):
                return fail(f"{section}/{label} vacuous flag false")
            if f"{section}:vacuous" not in bad["fail_reasons"]:
                return fail(f"{section}/{label} reason {bad['fail_reasons']}")
            fired.append(f"{section}:{label}")
            still_good = check_artifact(twin)
            if not still_good["pass"]:
                silent_on_good = False
                return fail("complete twin flipped after mutant check")

    if len(fired) != len(CHARTER_REQUIRED_OUTPUTS) * 7:
        return fail(f"expected 63 mutant firings, got {len(fired)}")

    if not is_vacuous([]) or not is_vacuous({"present": True}):
        return fail("is_vacuous missed empty list or present-checkbox")
    if is_vacuous(twin["outputs"]["recommendation"]):
        return fail("filled recommendation scored vacuous")

    payload = {
        "probe": "probe2-vacuous-section",
        "unit_id": "IMP-0356",
        "independent": True,
        "reviewer_id": "IMP-0356-probe2-vacuous-section",
        "starts_from": "complete_artifact twin + vacuous_mutants, not census ranking",
        "good_twin_pass": True,
        "silent_on_good_state": silent_on_good,
        "fired_on_bad_state": True,
        "n_mutants_fired": len(fired),
        "mutants": fired,
        "empty_list_vacuous": True,
        "present_checkbox_vacuous": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"mutants_fired={len(fired)} twin_pass=True "
        "empty_list=FAIL present_checkbox=FAIL"
    )
    print("SUCCESS:IMP-0356-probe2 empty-but-present section fails non-vacuity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
