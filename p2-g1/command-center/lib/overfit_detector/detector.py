"""Flag benchmark-gaming when visible/held-out gap exceeds the frozen threshold."""
from __future__ import annotations

from typing import Any, Sequence

from overfit_detector.corpus import Case
from overfit_detector.partition import HELD_OUT, VISIBLE, slice_of
from overfit_detector.threshold import PerRunThresholdTuneError, load_threshold

LANE = "benchmark-gaming"


def _accuracy(workflow: Any, cases: Sequence[Case]) -> float:
    if not cases:
        return 0.0
    hits = 0
    for case in cases:
        pred = workflow.predict(case)
        if pred == case.label:
            hits += 1
    return hits / len(cases)


def detect(
    workflow: Any,
    cases: Sequence[Case],
    *,
    threshold_override: float | None = None,
) -> dict[str, Any]:
    if threshold_override is not None:
        raise PerRunThresholdTuneError("detect() refuses threshold_override")
    spec = load_threshold()
    visible = [c for c in cases if slice_of(c.id) == VISIBLE]
    heldout = [c for c in cases if slice_of(c.id) == HELD_OUT]
    vis_acc = _accuracy(workflow, visible)
    held_acc = _accuracy(workflow, heldout)
    gap = vis_acc - held_acc
    if len(heldout) < int(spec.get("min_heldout_n") or 8):
        return {
            "flagged": False,
            "verdict": "INSUFFICIENT-EVIDENCE",
            "gap": gap,
            "visible_accuracy": vis_acc,
            "heldout_accuracy": held_acc,
            "visible_n": len(visible),
            "heldout_n": len(heldout),
            "refuter_lane": None,
            "threshold": spec,
        }
    flagged = gap > float(spec["gap_abs"])
    return {
        "flagged": flagged,
        "verdict": "FLAGGED" if flagged else "CLEAN",
        "gap": gap,
        "visible_accuracy": vis_acc,
        "heldout_accuracy": held_acc,
        "visible_n": len(visible),
        "heldout_n": len(heldout),
        "refuter_lane": LANE if flagged else None,
        "threshold": spec,
    }
