#!/usr/bin/env python3
"""Probe 2: randomized run-order ranking + 20% slowdown detection.

Mechanically different from probe 1: child-process wall clock via
time.monotonic (not perf_counter), cases shuffled with a recorded seed,
slowdown applied as extra hashlib rounds in the child.
"""
from __future__ import annotations

import json
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
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(H.REPO))
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


def slowdown_control() -> dict:
    case = H.CASE_BY_ID["capability-router"]
    base_rows = [child_run(case["id"], slowdown=1.0) for _ in range(H.N_REPS)]
    slow_rows = [child_run(case["id"], slowdown=H.SLOWDOWN) for _ in range(H.N_REPS)]
    base = H.summarize([r["elapsed_ms"] for r in base_rows])
    slow = H.summarize([r["elapsed_ms"] for r in slow_rows])
    ratio = slow["median_ms"] / base["median_ms"] if base["median_ms"] > 0 else 0.0
    detected = ratio >= H.SLOWDOWN_DETECT_FLOOR
    return {
        "control": "known-broken-20pct-slowdown",
        "case_id": case["id"],
        "input_size_bytes": case["bytes"],
        "injected_slowdown": H.SLOWDOWN,
        "detect_floor": H.SLOWDOWN_DETECT_FLOOR,
        "baseline": base,
        "slowed": slow,
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
