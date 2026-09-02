#!/usr/bin/env python3
"""Probe 2: fixed 60-task quality curve, rotated-label control, flood both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import engine as E  # noqa: E402
import flood_detector as FD  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    live = C.live_platform_records()
    tasks = C.load_task_set()
    if len(tasks) != C.N_TASKS:
        return fail(f"task set n={len(tasks)}")
    quality = E.quality_curve(live, tasks)
    flood = FD.both_states()
    precedent = E.skills_context_precedent()

    if quality["n_tasks"] != C.N_TASKS:
        return fail(f"n_tasks {quality['n_tasks']}")
    if [p["catalogue_size"] for p in quality["points"]] != list(C.SIZES):
        return fail("quality sizes drifted")
    if not quality["rotated_degrades"]:
        return fail(
            f"rotated labels did not degrade quality gold={quality['gold_accuracy_curve']} "
            f"rotated={quality['rotated_accuracy_curve']}"
        )
    if not quality["disabled_below_gold"]:
        return fail("router-disabled accuracy was not below gold accuracy")
    if any(p["flood_red_any"] for p in quality["points"]):
        return fail("budgeted quality path crossed the flood ceiling")
    if not flood["pass"]:
        return fail(
            f"flood detector both-states failed bad={flood['fired_on_bad_state']} "
            f"good={flood['silent_on_good_state']}"
        )
    if not flood["fired_on_bad_state"] or not flood["silent_on_good_state"]:
        return fail("flood detector is not two-sided")
    if not precedent["overflow_reproduced"]:
        return fail("skills-context-budget overflow was not reproduced")
    if not precedent["overflow_prevented"]:
        return fail("skills-context-budget overflow was not prevented")
    if precedent["naive_equals_char_quarter"]:
        return fail("naive token count is the banned len//4 estimate")

    out = REPO / C.OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact missing")
    text = out.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in text:
        return fail("catalog sentinel absent")
    meas = doc.get("measurements") or {}
    art_q = meas.get("quality") or {}
    if art_q.get("gold_accuracy_curve") != quality["gold_accuracy_curve"]:
        return fail("artifact gold accuracy curve drifted")
    if art_q.get("rotated_accuracy_curve") != quality["rotated_accuracy_curve"]:
        return fail("artifact rotated accuracy curve drifted")
    art_flood = meas.get("flood") or {}
    if art_flood.get("pass") is not True:
        return fail("artifact flood both-states not pass")
    art_prec = meas.get("precedent") or {}
    if art_prec.get("overflow_reproduced") is not True:
        return fail("artifact did not record overflow reproduction")
    if art_prec.get("overflow_prevented") is not True:
        return fail("artifact did not record overflow prevention")

    report = {
        "pass": True,
        "probe": "probe2-quality-curve",
        "unit_id": C.UNIT_ID,
        "n_tasks": C.N_TASKS,
        "sizes": list(C.SIZES),
        "gold_accuracy_curve": quality["gold_accuracy_curve"],
        "rotated_accuracy_curve": quality["rotated_accuracy_curve"],
        "disabled_accuracy_curve": quality["disabled_accuracy_curve"],
        "rotated_degrades": True,
        "quality_degraded_with_size": quality["quality_degraded_with_size"],
        "flood_fired_on_bad": flood["fired_on_bad_state"],
        "flood_silent_on_good": flood["silent_on_good_state"],
        "overflow_reproduced": True,
        "overflow_prevented": True,
        "naive_tokens": precedent["naive_tokens"],
        "budgeted_tokens": precedent["budgeted_tokens"],
        "live_n": len(live),
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"SUCCESS:{C.UNIT_ID}-probe2 quality gold={quality['gold_accuracy_curve']} "
        f"rotated={quality['rotated_accuracy_curve']} flood_both_states=PASS "
        f"overflow_reproduced_and_prevented"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
