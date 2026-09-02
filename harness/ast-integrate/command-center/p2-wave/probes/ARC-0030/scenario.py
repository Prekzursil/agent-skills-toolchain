"""Executable epistemic-silence scenario for ARC-0030.

Live corpus:
  command-center/p2-wave/probes/ARC-0010/registry.json (skill.council +
  wf.catalog-class.discovery-only).
Task (roles from skill.council body + catalog-class discovery):
  gold = skill.council.

A4 index-select never selects skill.council; selects the workflow;
gateway telemetry stays green. Body-aware control selects gold.
A1 always-on has gold resident. Uninstalling gold leaves A4 turn
metrics identical (still green, still the workflow).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from gateway import (  # noqa: E402
    DISTRACTOR_ID,
    GOLD_ID,
    TASK,
    load_registry_caps,
    metrics_all_green,
    run_gateway,
    turn_metric_view,
)


def run_scenario() -> dict[str, Any]:
    caps = load_registry_caps()
    ids = [str(c["id"]) for c in caps]
    if GOLD_ID not in ids or DISTRACTOR_ID not in ids:
        return {
            "pass": False,
            "error": f"live registry missing {GOLD_ID} or {DISTRACTOR_ID}",
            "ids": ids,
        }

    miss = run_gateway(TASK, caps, mode="a4_index")
    body = run_gateway(TASK, caps, mode="body_aware")
    always = run_gateway(TASK, caps, mode="a1_always_on")
    without = [c for c in caps if str(c["id"]) != GOLD_ID]
    uninstalled = run_gateway(TASK, without, mode="a4_index")

    gold_row = next(r for r in miss["index"] if r["capability_id"] == GOLD_ID)
    tel = miss["telemetry"]
    tel_u = uninstalled["telemetry"]
    green = metrics_all_green(tel)
    silent = (
        gold_row["installed"] is True
        and gold_row["indexed"] is True
        and miss["gold_selected"] is False
        and miss["distractor_selected"] is True
        and green is True
        and GOLD_ID not in miss["activated_ids"]
    )
    body_catches = body["gold_selected"] is True and GOLD_ID in body["activated_ids"]
    a1_catches = GOLD_ID in always["resident_bodies"]
    indistinguishable = turn_metric_view(tel) == turn_metric_view(tel_u)
    return {
        "pass": bool(silent and body_catches and a1_catches and indistinguishable),
        "task": TASK,
        "gold_id": GOLD_ID,
        "distractor_id": DISTRACTOR_ID,
        "installed_ids": ids,
        "a4_selected": miss["selected_ids"],
        "a4_activated": miss["activated_ids"],
        "a4_scores": miss["scores"],
        "a4_telemetry": tel,
        "a4_turn_metrics": turn_metric_view(tel),
        "metrics_all_green_on_miss": green,
        "gold_installed_and_indexed": True,
        "gold_never_selected": miss["gold_selected"] is False,
        "distractor_selected": miss["distractor_selected"] is True,
        "body_aware_selected": body["selected_ids"],
        "body_aware_selects_gold": body_catches,
        "a1_resident": always["resident_bodies"],
        "a1_gold_resident": a1_catches,
        "uninstalled_selected": uninstalled["selected_ids"],
        "uninstalled_turn_metrics": turn_metric_view(tel_u),
        "turn_metrics_identical_if_uninstalled": indistinguishable,
        "silent_miss_under_a4": silent,
        "body_aware_catches": body_catches,
        "a1_always_on_catches": a1_catches,
    }


if __name__ == "__main__":
    import sys

    out = run_scenario()
    print(json.dumps(out, indent=2, sort_keys=True))
    sys.exit(0 if out.get("pass") else 1)
