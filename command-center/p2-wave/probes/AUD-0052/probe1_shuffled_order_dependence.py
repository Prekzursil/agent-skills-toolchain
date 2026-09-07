#!/usr/bin/env python3
"""AUD-0052 NAMED PROBE 1: order-dependence census via 3 shuffled runs.

Catalog evidence_requirement Probe 1: "three shuffled runs with distinct
recorded seeds." A single shuffled run cannot show the shuffle plugin actually
did anything (it might be a no-op that happens to reproduce declaration
order); three runs with three distinct seeds, plus the catalog's own
tests_required control (assert recorded collection order differs between
seeds), are what makes a green result here meaningful.

Method:
  1. Run the full collectible test set (fixtures/collectible_scope.py,
     138 tests) once in plain declaration order -- the baseline.
  2. Run the SAME set three more times, each with a distinct
     --aud0052-seed passed to fixtures/aud0052_plugin.py, which reorders
     the collected item list with random.Random(seed).shuffle() (a real
     reorder, not a label) and records the post-shuffle node-id order.
  3. CONTROL (tests_required): assert the three recorded orders are
     pairwise distinct. If they were not, this probe would be reporting a
     shuffle that never happened, and the whole census below would be a
     false negative -- so that case is a hard FAIL, not a silent pass.
  4. order_dependent_candidates = tests that PASSED in the declaration-order
     baseline but FAILED in at least one of the three shuffled runs.
  5. Ground truth: fixtures/order_dependent/{test_a_writer,test_b_reader}.py
     is a deliberately planted order-dependent pair. The three seeds were
     chosen (by an offline simulation over the same collection order, not by
     hand-editing this probe's outcome) so that two of the three shuffles
     place test_b before test_a (must FAIL there) and one places test_a
     first (must PASS there) -- proving the detector fires on a real
     violation AND stays silent when the precondition happens to hold.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
FIXTURES = PROBE / "fixtures"
STATE_FILE = FIXTURES / "order_dependent" / "_shared_state.tmp"
OUT = PROBE / "probe1-shuffled-order-dependence.json"
RAW = PROBE / "probe1-shuffled-order-dependence.raw.txt"

SEEDS = [1001, 2002, 5005]
GROUND_TRUTH_A = "test_a_writes_flag"
GROUND_TRUTH_B = "test_b_requires_writer_flag"


def target_args() -> list[str]:
    sys.path.insert(0, str(FIXTURES))
    import collectible_scope  # noqa: E402

    return list(collectible_scope.TARGET_ARGS)


def run_pytest(seed: int | None, tmpdir: Path) -> tuple[int, str, list[str], dict[str, str]]:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    order_path = tmpdir / f"order-{seed}.txt"
    results_path = tmpdir / f"results-{seed}.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FIXTURES) + os.pathsep + env.get("PYTHONPATH", "")
    env["AUD0052_ORDER_PATH"] = str(order_path)
    env["AUD0052_RESULTS_PATH"] = str(results_path)
    args = [
        sys.executable,
        "-m",
        "pytest",
        *target_args(),
        "-p",
        "aud0052_plugin",
        "-q",
        "--tb=no",
        "-p",
        "no:cacheprovider",
    ]
    if seed is not None:
        args.append(f"--aud0052-seed={seed}")
    try:
        r = subprocess.run(
            args, cwd=str(REPO), capture_output=True, text=True, timeout=180, env=env
        )
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired as e:
        rc, out = 124, f"TIMEOUT: {e}"
    order = (
        order_path.read_text(encoding="utf-8").splitlines()
        if order_path.is_file()
        else []
    )
    results = (
        json.loads(results_path.read_text(encoding="utf-8"))
        if results_path.is_file()
        else {}
    )
    return rc, out, order, results


def main() -> int:
    lines: list[str] = ["AUD-0052 NAMED PROBE 1: shuffled-order-dependence census", "unit=AUD-0052"]
    with tempfile.TemporaryDirectory(prefix="aud0052-p1-") as td:
        tmp = Path(td)

        base_rc, base_out, base_order, base_results = run_pytest(None, tmp)
        lines.append(
            f"BASELINE(declaration-order) rc={base_rc} collected={len(base_order)} "
            f"results={len(base_results)}"
        )

        seed_orders: dict[int, list[str]] = {}
        seed_results: dict[int, dict[str, str]] = {}
        seed_rcs: dict[int, int] = {}
        for seed in SEEDS:
            rc, out, order, results = run_pytest(seed, tmp)
            seed_orders[seed] = order
            seed_results[seed] = results
            seed_rcs[seed] = rc
            lines.append(
                f"SHUFFLE seed={seed} rc={rc} collected={len(order)} "
                f"results={len(results)} first3={order[:3]}"
            )

    # CONTROL (tests_required): the shuffle plugin must actually reorder --
    # assert the recorded collection order differs between seeds.
    orders_list = [seed_orders[s] for s in SEEDS]
    pairwise_distinct = all(
        orders_list[i] != orders_list[j]
        for i in range(len(orders_list))
        for j in range(i + 1, len(orders_list))
    )
    any_differs_from_baseline = any(o != base_order for o in orders_list)
    same_membership = all(sorted(o) == sorted(base_order) for o in orders_list) and bool(
        base_order
    )
    shuffle_control_ok = pairwise_distinct and any_differs_from_baseline and same_membership
    lines.append(
        f"CONTROL shuffle_actually_reorders pairwise_distinct={pairwise_distinct} "
        f"any_differs_from_baseline={any_differs_from_baseline} "
        f"same_test_membership={same_membership} ok={shuffle_control_ok}"
    )

    order_dependent_candidates: list[dict] = []
    if shuffle_control_ok:
        for nodeid, base_outcome in base_results.items():
            if base_outcome != "passed":
                continue
            for seed in SEEDS:
                outcome = seed_results.get(seed, {}).get(nodeid)
                if outcome is not None and outcome != "passed":
                    order_dependent_candidates.append(
                        {
                            "nodeid": nodeid,
                            "baseline_outcome": base_outcome,
                            "seed": seed,
                            "shuffled_outcome": outcome,
                        }
                    )
                    break

    gt_b_flagged = any(
        GROUND_TRUTH_B in c["nodeid"] for c in order_dependent_candidates
    )
    b_nodeid = next(
        (nid for nid in base_results if GROUND_TRUTH_B in nid), None
    )
    gt_b_seeds_failed = sorted(
        seed
        for seed in SEEDS
        if b_nodeid is not None
        and seed_results.get(seed, {}).get(b_nodeid) not in (None, "passed")
    )
    gt_a_present_all_seeds = all(
        any(GROUND_TRUTH_A in nid for nid in seed_orders[s]) for s in SEEDS
    )
    ground_truth_ok = (
        shuffle_control_ok
        and gt_b_flagged
        and gt_b_seeds_failed == [1001, 2002]
        and gt_a_present_all_seeds
    )
    lines.append(
        f"GROUND-TRUTH planted order-dependent pair test_a_writes_flag/"
        f"test_b_requires_writer_flag: flagged={gt_b_flagged} "
        f"failed_on_seeds={gt_b_seeds_failed} (expected [1001, 2002]) "
        f"ok={ground_truth_ok}"
    )

    baseline_all_collectible_present = len(base_order) == 138
    lines.append(f"COLLECTIBLE-COUNT baseline_collected={len(base_order)} expected=138")

    ok = shuffle_control_ok and ground_truth_ok
    result = {
        "ok": ok,
        "unit": "AUD-0052",
        "probe": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seeds": SEEDS,
        "baseline_rc": base_rc,
        "baseline_collected_count": len(base_order),
        "baseline_order_first10": base_order[:10],
        "seed_rcs": seed_rcs,
        "seed_collected_counts": {s: len(seed_orders[s]) for s in SEEDS},
        "seed_order_first10": {s: seed_orders[s][:10] for s in SEEDS},
        "shuffle_control_ok": shuffle_control_ok,
        "shuffle_control": {
            "pairwise_distinct": pairwise_distinct,
            "any_differs_from_baseline": any_differs_from_baseline,
            "same_test_membership": same_membership,
        },
        "order_dependent_candidates_count": len(order_dependent_candidates),
        "order_dependent_candidates": order_dependent_candidates,
        "ground_truth_ok": ground_truth_ok,
        "ground_truth": {
            "flagged": gt_b_flagged,
            "failed_on_seeds": gt_b_seeds_failed,
            "expected_failed_on_seeds": [1001, 2002],
            "a_present_all_seeds": gt_a_present_all_seeds,
        },
        "baseline_all_collectible_present": baseline_all_collectible_present,
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines.append(
        f"order_dependent_candidates_count={len(order_dependent_candidates)} "
        f"of baseline_collected={len(base_order)}"
    )
    for c in order_dependent_candidates:
        lines.append(
            f"  ORDER-DEP {c['nodeid']} baseline=passed seed={c['seed']} "
            f"shuffled={c['shuffled_outcome']}"
        )
    lines.append(f"ok={ok}")
    lines.append("SUCCESS:AUD-0052-probe1" if ok else "FAILED:AUD-0052-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
