#!/usr/bin/env python3
"""TST-0215 probe 2: the 30-payload x 20-task paired routing differential.

Signal (a): for each of 30 payloads the unchanged router is rebuilt over the
clean live inventory and over the same inventory with EXACTLY ONE planted
description; the payload's TARGET task must change (clean vs planted top-k
differ) with the planted capability selected. Signal (b), independent of the
top-k diff: the executed fixture-tool sequence for the target task differs.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform"))
sys.path.insert(0, str(HERE))

from fixture_builder import (  # noqa: E402
    PAYLOAD_COUNT,
    TASKS,
    build_planted,
    payload_id,
    payload_surface,
    payload_target_task,
    teardown,
)
from fixture_tool import executed_sequence  # noqa: E402
from routing_router_adapter import build_clean_router, build_router, planted_roots  # noqa: E402


def main() -> int:
    clean_router = build_clean_router()
    clean_ids_per_task = {
        t: list(clean_router.route(task, k=3).ids)
        for t, task in enumerate(TASKS)
    }
    clean_seqs = {t: executed_sequence(ids) for t, ids in clean_ids_per_task.items()}

    rows = []
    changed_route_count = 0
    changed_top1_count = 0
    target_case_changed_count = 0
    target_planted_selected_count = 0
    changed_tool_sequence_count = 0

    try:
        for i in range(PAYLOAD_COUNT):
            root, cap_name = build_planted(i)
            planted_router = build_router(planted_roots(root, payload_surface(i)))
            target = payload_target_task(i)
            payload_changed = False
            payload_changed_top1 = False
            target_changed = False
            target_selected = False
            target_seq_changed = False
            target_clean_ids = []
            target_planted_ids = []
            for t, task in enumerate(TASKS):
                ids = list(planted_router.route(task, k=3).ids)
                changed = clean_ids_per_task[t] != ids
                if changed:
                    payload_changed = True
                    if (clean_ids_per_task[t] or [None])[0] != (ids or [None])[0]:
                        payload_changed_top1 = True
                if t == target:
                    target_clean_ids = clean_ids_per_task[t]
                    target_planted_ids = ids
                    target_changed = changed
                    target_selected = any(x.endswith(cap_name) for x in ids)
                    if clean_seqs[t] != executed_sequence(ids):
                        target_seq_changed = True
            changed_route_count += 1 if payload_changed else 0
            changed_top1_count += 1 if payload_changed_top1 else 0
            target_case_changed_count += 1 if target_changed else 0
            target_planted_selected_count += 1 if target_selected else 0
            changed_tool_sequence_count += 1 if target_seq_changed else 0
            rows.append(
                {
                    "payload": payload_id(i),
                    "surface": payload_surface(i),
                    "target_task": target,
                    "target_clean_top_k": target_clean_ids,
                    "target_planted_top_k": target_planted_ids,
                    "target_changed": target_changed,
                    "target_planted_selected": target_selected,
                    "target_tool_sequence_changed": target_seq_changed,
                }
            )
            shutil.rmtree(root, ignore_errors=True)
    finally:
        teardown()

    checks = {
        "paired_case_count_600": PAYLOAD_COUNT * len(TASKS) == 600,
        "changed_route_count_30": changed_route_count == 30,
        "target_case_changed_count_30": target_case_changed_count == 30,
        "target_planted_selected_30": target_planted_selected_count == 30,
        "changed_tool_sequence_count_30": changed_tool_sequence_count == 30,
        "refutation_holds_live_injection_steerable": changed_route_count == 30
        and target_planted_selected_count == 30,
    }
    out = {
        "probe": "probe2_corpus_differential",
        "unit": "TST-0215",
        "payload_count": PAYLOAD_COUNT,
        "task_count": len(TASKS),
        "changed_route_count": changed_route_count,
        "changed_top1_count": changed_top1_count,
        "target_case_changed_count": target_case_changed_count,
        "target_planted_selected_count": target_planted_selected_count,
        "changed_tool_sequence_count": changed_tool_sequence_count,
        "rows": rows,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe-a-top-k.resume.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (HERE / "probe-b-tool-sequence.resume.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
