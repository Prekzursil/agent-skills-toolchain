#!/usr/bin/env python3
"""Probe 2: randomized run-order ranking + 20% slowdown detection.

Mechanically different from probe 1: child-process wall clock via
time.monotonic (not perf_counter), cases shuffled with a recorded seed,
slowdown applied as extra hashlib rounds in the child.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

OUT = HERE / "probe2-order-slowdown.raw.json"
WORKER = HERE / "harness.py"
ORDER_SEEDS = (1801, 1802, 1803, 1804, 1805)
SAMPLES_PER_CELL = 5


def _worker_env() -> dict:
    # Python 3.14 argparse colorizer lazily imports _colorize -> dataclasses
    # -> inspect -> annotationlib -> ast; tools/ast.py on an inherited
    # PYTHONPATH shadows stdlib ast and closes an import cycle that kills
    # the worker before it measures anything (measured 2026-10-24, shard 5).
    # The worker is stdlib-only, so it runs with PYTHONPATH scrubbed.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def child_run(case_id: str, *, slowdown: float = 1.0) -> dict:
    t0 = time.monotonic()
    cmd = [
        sys.executable,
        "-B",
        str(WORKER),
        "--once",
        case_id,
        "--clock",
        "monotonic",
        "--slowdown",
        str(slowdown),
    ]
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(H.REPO),
        env=_worker_env(),
    )
    wall_ms = (time.monotonic() - t0) * 1000.0
    if p.returncode != 0:
        raise SystemExit(
            f"FAILED:CNF-0180-probe2 worker rc={p.returncode} {p.stderr[-400:]}"
        )
    inner = json.loads(p.stdout.splitlines()[-1])
    if int(inner.get("input_size_bytes") or 0) <= 0:
        raise SystemExit(f"FAILED:CNF-0180-probe2 empty input slipped through: {inner}")
    inner["parent_monotonic_wall_ms"] = wall_ms
    inner["instrument"] = "subprocess+time.monotonic"
    return inner


def empty_child_control() -> dict:
    t0 = time.monotonic()
    p = subprocess.run(
        [sys.executable, "-B", str(WORKER), "--empty", "--clock", "monotonic"],
        capture_output=True,
        text=True,
        cwd=str(H.REPO),
        env=_worker_env(),
    )
    wall_ms = (time.monotonic() - t0) * 1000.0
    try:
        inner = json.loads((p.stdout or "").splitlines()[-1]) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        inner = {"parse_error": True, "stdout": (p.stdout or "")[-200:]}
    emitted = inner.get("elapsed_ms") not in (None, "")
    ok = p.returncode != 0 and inner.get("empty_input") is True and not emitted
    return {
        "control": "empty-input-child",
        "exit_code": p.returncode,
        "elapsed_ms_emitted": inner.get("elapsed_ms"),
        "parent_monotonic_wall_ms": wall_ms,
        "pass": ok,
        "child": inner,
    }


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def order_control() -> dict:
    rankings = []
    cells = []
    for seed in ORDER_SEEDS:
        rng = random.Random(seed)
        order = list(H.CASE_BY_ID)
        rng.shuffle(order)
        medians = {}
        for cid in order:
            samples = [child_run(cid)["elapsed_ms"] for _ in range(SAMPLES_PER_CELL)]
            medians[cid] = median(samples)
            cells.append(
                {
                    "seed": seed,
                    "run_order": order,
                    "case_id": cid,
                    "input_size_bytes": H.CASE_BY_ID[cid]["bytes"],
                    "n": len(samples),
                    "median_ms": medians[cid],
                    "raw_ms": samples,
                }
            )
        ranking = H.rank_ids(medians)
        rankings.append({"seed": seed, "order": order, "ranking": ranking, "medians_ms": medians})
    expected = H.rank_ids(
        {c["id"]: float(c["bytes"] * c["rounds"]) for c in H.CASES}
    )
    observed = [r["ranking"] for r in rankings]
    stable = all(r == observed[0] for r in observed)
    matches_work = observed[0] == expected
    return {
        "control": "randomized-order",
        "seeds": list(ORDER_SEEDS),
        "expected_ranking_by_work": expected,
        "rankings": rankings,
        "cells": cells,
        "stable": stable,
        "matches_work_order": matches_work,
        "pass": stable and matches_work,
    }


def slowdown_control(n_pairs: int = 41) -> dict:
    # History: n=11/arm independent arms measured ratio 1.09 vs the 1.10
    # floor; 41/arm still measured 1.0729 on 2026-10-24 because arm-LEVEL
    # clock drift (the whole baseline arm runs before the whole slowed arm)
    # deflates the between-arm median ratio even though the injected work
    # ratio is 38/32 = 1.1875. Repair (shard-5 resume): interleave the arms
    # as back-to-back pairs and take the MEDIAN OF PER-PAIR RATIOS, which
    # cancels drift between arms. Detection floor and injected effect are
    # unchanged; only the estimator changed.
    case = H.CASE_BY_ID["capability-router"]
    base_rows: list = []
    slow_rows: list = []
    pair_ratios: list = []
    for i in range(n_pairs):
        # alternate position so first-position warmup cannot bias either arm
        if i % 2 == 0:
            b = child_run(case["id"], slowdown=1.0)          # base first
            s = child_run(case["id"], slowdown=H.SLOWDOWN)   # slowed second
        else:
            s = child_run(case["id"], slowdown=H.SLOWDOWN)   # position-balanced:
            b = child_run(case["id"], slowdown=1.0)          # slowed first
        # b is always the slowdown=1.0 run and s the slowed run; only the
        # launch order alternates, so warmup/position cannot bias either arm.
        base_rows.append(b)
        slow_rows.append(s)
        if b["elapsed_ms"] > 0:
            pair_ratios.append(s["elapsed_ms"] / b["elapsed_ms"])
    base = H.summarize([r["elapsed_ms"] for r in base_rows])
    slow = H.summarize([r["elapsed_ms"] for r in slow_rows])
    ratio = median(pair_ratios) if pair_ratios else 0.0
    detected = ratio >= H.SLOWDOWN_DETECT_FLOOR
    return {
        "control": "known-broken-20pct-slowdown",
        "estimator": "median of per-pair ratios (interleaved pairs, drift-cancelling)",
        "n_pairs": n_pairs,
        "case_id": case["id"],
        "input_size_bytes": case["bytes"],
        "injected_slowdown": H.SLOWDOWN,
        "detect_floor": H.SLOWDOWN_DETECT_FLOOR,
        "baseline": base,
        "slowed": slow,
        "pair_ratios": pair_ratios,
        "median_ratio": ratio,
        "detected": detected,
        "pass": detected,
        "baseline_runs": base_rows,
        "slowed_runs": slow_rows,
        "rollback_note": "baseline arm is the unslowed child; ranking uses unslowed cases only",
    }


def main() -> int:
    pre = H.machine_state()
    empty = empty_child_control()
    if not empty["pass"]:
        print("FAILED:CNF-0180-probe2 child empty-input control did not fail")
        print(json.dumps(empty, sort_keys=True))
        return 1
    order = order_control()
    if not order["pass"]:
        print("FAILED:CNF-0180-probe2 ranking not stable or not work-ordered")
        print(json.dumps({k: order[k] for k in ("stable", "matches_work_order", "rankings")}, indent=2))
        return 1
    slow = slowdown_control()
    if not slow["pass"]:
        print(
            f"FAILED:CNF-0180-probe2 20pct slowdown not detected "
            f"ratio={slow['median_ratio']:.4f} floor={H.SLOWDOWN_DETECT_FLOOR}"
        )
        return 1
    post = H.machine_state()
    doc = {
        "probe": "probe2-order-and-slowdown",
        "unit_id": "CNF-0180",
        "instrument": "subprocess python -B harness.py --clock monotonic; parent time.monotonic wall",
        "empty_input_control": empty,
        "order_control": {
            "control": order["control"],
            "seeds": order["seeds"],
            "expected_ranking_by_work": order["expected_ranking_by_work"],
            "rankings": order["rankings"],
            "stable": order["stable"],
            "matches_work_order": order["matches_work_order"],
            "pass": order["pass"],
        },
        "order_cells": order["cells"],
        "slowdown_control": slow,
        "machine_state_before": pre,
        "machine_state_after": post,
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"empty_fail={empty['pass']} rank_stable={order['stable']} "
        f"rank={order['rankings'][0]['ranking']} "
        f"slowdown_ratio={slow['median_ratio']:.4f} detected={slow['detected']}"
    )
    print("SUCCESS:CNF-0180-probe2 randomized order and 20-percent slowdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
