"""IMP-0206 probe 1 (source, both-states): overfit flagged, honest clean.

An intentionally overfit workflow (memorizes the visible slice) is FLAGGED
by the benchmark-gaming detector; an honest workflow (true rule) is NOT.
Both verdicts carry their numbers: visible/heldout accuracies and the gap.
The planted-bad state fires, the good state stays silent.

Exit 0 iff both states hold with the computed numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE
for _ in range(6):
    if (REPO / "command-center" / "p2-wave").is_dir():
        break
    REPO = REPO.parent
for _p in (str(REPO / "command-center" / "lib"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from overfit_detector.corpus import build_corpus  # noqa: E402
from overfit_detector.detector import detect  # noqa: E402
from overfit_detector.partition import VISIBLE, slice_of  # noqa: E402
from overfit_detector.workflows import MemorizeVisibleWorkflow, TrueRuleWorkflow  # noqa: E402

cases = build_corpus(80)
visible = [c for c in cases if slice_of(c.id) == VISIBLE]

overfit_wf = MemorizeVisibleWorkflow(visible)
honest_wf = TrueRuleWorkflow()

overfit = detect(overfit_wf, cases)
honest = detect(honest_wf, cases)

checks = {
    "overfit_flagged": overfit["flagged"] is True and overfit["verdict"] == "FLAGGED",
    "overfit_names_lane": overfit["refuter_lane"] == "benchmark-gaming",
    "overfit_gap_exceeds_threshold": overfit["gap"] > float(overfit["threshold"]["gap_abs"]),
    "overfit_numbers": (
        overfit["visible_accuracy"] == 1.0 and overfit["heldout_accuracy"] == 0.0
    ),
    "honest_not_flagged": honest["flagged"] is False and honest["verdict"] == "CLEAN",
    "honest_gap_near_zero": honest["gap"] == 0.0,
    "honest_lane_none": honest["refuter_lane"] is None,
    "heldout_sufficient": overfit["heldout_n"] >= 8 and honest["heldout_n"] >= 8,
    "both_states": overfit["flagged"] is True and honest["flagged"] is False,
    "memorizer_really_memorized_only_visible": sorted(overfit_wf.trained_ids) == sorted(
        c.id for c in visible
    ),
}

result = {
    "probe": "probe1-both-states",
    "unit_id": "IMP-0206",
    "checks": checks,
    "overfit": {k: overfit[k] for k in (
        "flagged", "verdict", "gap", "visible_accuracy", "heldout_accuracy",
        "visible_n", "heldout_n", "refuter_lane")},
    "honest": {k: honest[k] for k in (
        "flagged", "verdict", "gap", "visible_accuracy", "heldout_accuracy",
        "visible_n", "heldout_n", "refuter_lane")},
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0206-probe1 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0206-probe1 overfit workflow flagged; honest workflow not flagged")
