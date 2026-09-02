#!/usr/bin/env python3
"""Probe 1: every strategy on the identical published task set; recount matches artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import harness as H  # noqa: E402
import schema_offline as SO  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0105-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != C.UNIT_ID:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    kind = report.get("kind") or doc.get("report_kind")
    if kind != "measurement-run":
        return fail(f"report.kind={kind}")

    errors = sorted(
        SO.validator().iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errors:
        return fail(f"schema {errors[0].message}")

    live = H.evaluate()
    if not live.get("all_strategies_share_task_ids"):
        return fail("strategies did not share task ids")
    art_ids = list(
        (report.get("task_set") or doc.get("task_set") or {}).get("task_ids") or []
    )
    if art_ids != live["task_ids"]:
        return fail(f"task_ids mismatch art={art_ids} live={live['task_ids']}")

    art_counts = report.get("wrong_selection_counts") or doc.get(
        "wrong_selection_counts"
    ) or {}
    live_counts = {
        **live.get("named_counts", {}),
        "random": live["random_wrong_selection_count"],
    }
    if "named_counts" in live:
        live_counts = {
            **live["named_counts"],
            "random": live["random_wrong_selection_count"],
        }
    for name in C.ALL_STRATEGIES:
        live_n = int(live["per_strategy"][name]["wrong_selection_count"])
        art_n = art_counts.get(name)
        print(f"strategy {name} live_wrong={live_n} artifact_wrong={art_n}")
        if art_n != live_n:
            return fail(f"count mismatch {name} live={live_n} art={art_n}")

    named = {n: live_counts[n] for n in C.NAMED_STRATEGIES}
    best = min(named.values())
    random_n = live["random_wrong_selection_count"]
    if random_n <= best:
        return fail(f"random {random_n} not worse than best named {best}")

    winner = report.get("winner") or doc.get("winner") or {}
    if winner.get("strategy") not in C.NAMED_STRATEGIES:
        return fail(f"winner {winner}")
    if int(winner.get("wrong_selection_count")) != best:
        return fail("winner count != live min named")

    print(
        f"n_tasks={live['n_tasks']} best_named={min(named, key=named.get)} "
        f"best_wrong={best} random_wrong={random_n}"
    )
    print("SUCCESS:RES-0105-probe1 shared task set; live counts match artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
