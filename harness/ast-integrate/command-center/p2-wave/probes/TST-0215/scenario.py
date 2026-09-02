#!/usr/bin/env python3
"""Live measurements for TST-0215: injection invariance + rename detector.

Two independent signals, computed separately:
  (a) router top-k ids
  (b) executor tool sequence
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import (  # noqa: E402
    CATALOG,
    DECOY_ID,
    PAYLOADS,
    RENAME_NEW_ID,
    RENAME_OLD_ID,
    TASKS,
    assert_sizes,
)
from executor import execute  # noqa: E402
from router import (  # noqa: E402
    inject_prose,
    rename_capability,
    top_k_ids,
)


def _fp(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def decide(task: dict, catalog: list[dict], *, scorer: str) -> dict:
    ids = top_k_ids(task["text"], catalog, scorer=scorer)
    return {
        "task_id": task["id"],
        "top_k": ids,
        "tool_sequence": execute(ids, catalog),
    }


def stub_always_equal(_a: dict, _b: dict) -> bool:
    """Known-broken comparator: always reports identical routing."""
    return True


def compare_live(a: dict, b: dict) -> dict:
    top_k_same = a["top_k"] == b["top_k"]
    tools_same = a["tool_sequence"] == b["tool_sequence"]
    return {
        "identical": top_k_same and tools_same,
        "top_k_same": top_k_same,
        "tools_same": tools_same,
    }


def run_invariance() -> dict:
    assert_sizes()
    clean_by_task = {t["id"]: decide(t, CATALOG, scorer="data") for t in TASKS}
    pairs = []
    n_top_k_mismatch = 0
    n_tools_mismatch = 0
    naive_diverged = 0
    follow_diverged = 0
    for payload_i, payload in enumerate(PAYLOADS, start=1):
        for task in TASKS:
            injected = inject_prose(CATALOG, payload, task["text"], DECOY_ID)
            clean = clean_by_task[task["id"]]
            data_inj = decide(task, injected, scorer="data")
            cmp = compare_live(clean, data_inj)
            if not cmp["top_k_same"]:
                n_top_k_mismatch += 1
            if not cmp["tools_same"]:
                n_tools_mismatch += 1
            naive = decide(task, injected, scorer="naive")
            follow = decide(task, injected, scorer="follow")
            if naive["top_k"] != clean["top_k"] or naive["tool_sequence"] != clean["tool_sequence"]:
                naive_diverged += 1
            if follow["top_k"] != clean["top_k"] or follow["tool_sequence"] != clean["tool_sequence"]:
                follow_diverged += 1
            pairs.append(
                {
                    "payload_i": payload_i,
                    "task_id": task["id"],
                    "data_identical": cmp["identical"],
                }
            )
    n_pairs = len(TASKS) * len(PAYLOADS)
    clean_topk = {tid: row["top_k"] for tid, row in clean_by_task.items()}
    clean_tools = {tid: row["tool_sequence"] for tid, row in clean_by_task.items()}
    decoy_wins_clean = sum(1 for row in clean_by_task.values() if row["top_k"][0] == DECOY_ID)
    return {
        "n_tasks": len(TASKS),
        "n_payloads": len(PAYLOADS),
        "n_pairs": n_pairs,
        "n_top_k_mismatch": n_top_k_mismatch,
        "n_tools_mismatch": n_tools_mismatch,
        "data_invariant": n_top_k_mismatch == 0 and n_tools_mismatch == 0,
        "naive_diverged_pairs": naive_diverged,
        "follow_diverged_pairs": follow_diverged,
        "corpus_has_teeth": naive_diverged > 0 and follow_diverged > 0,
        "decoy_wins_clean": decoy_wins_clean,
        "clean_topk": clean_topk,
        "clean_tools": clean_tools,
        "clean_topk_sha256": _fp(clean_topk),
        "clean_tools_sha256": _fp(clean_tools),
        "pairs_identical_count": sum(1 for p in pairs if p["data_identical"]),
        "pass": (
            n_pairs == 600
            and n_top_k_mismatch == 0
            and n_tools_mismatch == 0
            and naive_diverged > 0
            and follow_diverged > 0
            and decoy_wins_clean == 0
        ),
    }


def run_rename_detector() -> dict:
    assert_sizes()
    renamed = rename_capability(CATALOG, RENAME_OLD_ID, RENAME_NEW_ID)
    before = []
    after = []
    changed = []
    stub_misses = 0
    for task in TASKS:
        b = decide(task, CATALOG, scorer="data")
        a = decide(task, renamed, scorer="data")
        live = compare_live(b, a)
        stub = stub_always_equal(b, a)
        before.append(b)
        after.append(a)
        if not live["identical"]:
            changed.append(
                {
                    "task_id": task["id"],
                    "before_top_k": b["top_k"],
                    "after_top_k": a["top_k"],
                    "before_tools": b["tool_sequence"],
                    "after_tools": a["tool_sequence"],
                }
            )
        if (not live["identical"]) and stub:
            stub_misses += 1
    detected = len(changed) > 0
    git_tasks = [c for c in changed if RENAME_OLD_ID in c["before_top_k"]]
    return {
        "detected": detected,
        "n_tasks_changed": len(changed),
        "n_git_tasks_changed": len(git_tasks),
        "stub_always_equal_misses": stub_misses,
        "stub_is_known_broken": stub_misses == len(changed) and detected,
        "sample": changed[:5],
        "rename": {"old": RENAME_OLD_ID, "new": RENAME_NEW_ID},
        "before_topk_sha256": _fp([r["top_k"] for r in before]),
        "after_topk_sha256": _fp([r["top_k"] for r in after]),
        "pass": detected and stub_misses == len(changed) and len(git_tasks) >= 1,
    }


def run_all() -> dict:
    inv = run_invariance()
    det = run_rename_detector()
    return {
        "invariance": inv,
        "rename_detector": det,
        "pass": bool(inv.get("pass") and det.get("pass")),
    }
