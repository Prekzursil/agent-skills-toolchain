#!/usr/bin/env python3
"""Fix cycle 1 for CNF-0180 probe2 (measured 2026-10-24, shard-5 resume).

Defect: slowdown_control compared medians of two INDEPENDENT arms (baseline
arm fully precedes the slowed arm). On this host the arm-level clock drift
(thermal/turbo) deflates the median ratio below the 1.10 detection floor even
though the injected work ratio is 38/32 = 1.1875 (measured 1.0729 at n=41).

Repair: interleave the two arms as back-to-back PAIRS and take the median of
per-pair ratios. Pairing cancels drift; floor (H.SLOWDOWN_DETECT_FLOOR) and
injected effect (H.SLOWDOWN) are UNCHANGED. Baseline/slowed summaries are
still reported from the same samples, so the published distribution shape is
preserved.
"""
from pathlib import Path

P = Path(__file__).resolve().parents[1] / (
    "command-center/p2-wave/probes/CNF-0180/probe2_order_and_slowdown.py"
)
src = P.read_text(encoding="utf-8")

OLD = '''def slowdown_control(n_per_arm: int = 41) -> dict:
    # n=11 per arm was measured too noisy on this host for a 20% effect on
    # ~0.4 ms of child-measured hashing work (ratio landed at 1.09 vs the
    # 1.10 floor); 41 per arm tightens the medians against the known work
    # ratio 38/32 = 1.1875. Sample count only - floor and effect unchanged.
    case = H.CASE_BY_ID["capability-router"]
    base_rows = [child_run(case["id"], slowdown=1.0) for _ in range(n_per_arm)]
    slow_rows = [child_run(case["id"], slowdown=H.SLOWDOWN) for _ in range(n_per_arm)]
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
    }'''

NEW = '''def slowdown_control(n_pairs: int = 41) -> dict:
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
    }'''

assert OLD in src, "slowdown_control block not found verbatim"
P.write_text(src.replace(OLD, NEW), encoding="utf-8", newline="\n")
print("patched", P)
