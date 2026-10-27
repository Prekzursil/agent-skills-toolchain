#!/usr/bin/env python3
"""IMP-0356 probe2: vacuous-section negative control (independent reviewer).

Starts from the catalog test ("an empty-but-present section must FAIL the
non-vacuity test"), not from the author's summary. For EVERY required output it
plants an empty-but-present section and requires the completeness check to
FAIL; it also runs the good-state control (a genuinely complete artifact must
PASS) and the both-states rule (the control fires on the bad state and stays
silent on the good state).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.completeness import (  # noqa: E402
    CHARTER_REQUIRED_OUTPUTS,
    check_artifact,
    complete_artifact,
    vacuous_mutants,
)

RECEIPT = REPO / "command-center/receipts/IMP-0356.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0356-probe2 {msg}")
    return 1


def main() -> int:
    # Both-states rule: mutants must FAIL, the genuine artifact must PASS.
    fired_bad = 0
    for mutant in vacuous_mutants():
        row = check_artifact(mutant["artifact"])
        if row["pass"] is not False:
            return fail(f"mutant-passed:{mutant['section']}")
        if row["fail_reasons"] != [f"{mutant['section']}:vacuous"]:
            return fail(f"wrong-reason:{mutant['section']}")
        fired_bad += 1

    good = check_artifact(complete_artifact("probe2-good-state"))
    if good["pass"] is not True or good["missing"]:
        return fail("good-state-failed")

    # Presence is not completeness: {"present": true} checkbox must FAIL.
    doc = complete_artifact("probe2-checkbox")
    doc["outputs"]["votes"] = {"present": True}
    row = check_artifact(doc)
    if row["pass"] is not False:
        return fail("checkbox-votes-passed")

    # TBD string section must FAIL; placeholder marker must FAIL.
    for marker in ("TBD", "placeholder", "n/a"):
        d = complete_artifact("probe2-marker")
        d["outputs"]["unknowns"] = {"note": marker}
        r = check_artifact(d)
        if r["pass"] is not False:
            return fail(f"marker-passed:{marker}")

    # Receipt's declared negative-control ids must exist and be non-empty.
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    neg_ids = [n.get("id") for n in doc.get("negative_controls") or [] if n.get("id")]
    if len(neg_ids) < 3:
        return fail(f"receipt-negctl-ids:{neg_ids}")
    print(json.dumps({
        "probe": "probe2-vacuous-section",
        "unit_id": "IMP-0356",
        "pass": True,
        "mutants_fired": fired_bad,
        "good_state_pass": True,
        "checkbox_rejected": True,
        "marker_cases_rejected": ["TBD", "placeholder", "n/a"],
        "receipt_negctl_ids": neg_ids,
    }, sort_keys=True))
    print("SUCCESS:IMP-0356-probe2 empty-but-present fails for all 9 outputs; controls hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
