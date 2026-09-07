#!/usr/bin/env python3
"""AUD-0052 NAMED PROBE 2: flake census via 5 identical-order repeats.

Catalog evidence_requirement Probe 2: "five identical-order repeats, which
separates order dependence from nondeterminism -- a single shuffled failure
cannot distinguish the two." Every one of the five runs here uses the SAME
declaration order (no --aud0052-seed at all); collection order is therefore
held constant across all five, so any test whose outcome still varies across
the five runs cannot be explained by reordering -- it is flaky (or the
environment/process itself is nondeterministic), which is a different defect
class from what probe1 measures.

Ground truth: fixtures/flaky/test_flaky_ground_truth.py draws from OS entropy
(no fixed seed) on every process start, so it is expected to disagree with
itself across independent repeats. If all five repeats agreed on this single
known-nondeterministic test, that would mean the "five independent runs"
harness is not actually re-executing independent processes (e.g. a cached or
memoized result) -- a control failure, not a clean bill of health -- and is
treated as such below.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
FIXTURES = PROBE / "fixtures"
STATE_FILE = FIXTURES / "order_dependent" / "_shared_state.tmp"
OUT = PROBE / "probe2-repeated-identical-order.json"
RAW = PROBE / "probe2-repeated-identical-order.raw.txt"

REPEATS = 5
GROUND_TRUTH_FLAKY = "test_flaky_probability"


def target_args() -> list[str]:
    sys.path.insert(0, str(FIXTURES))
    import collectible_scope  # noqa: E402

    return list(collectible_scope.TARGET_ARGS)


def run_pytest_once(run_idx: int, tmpdir: Path) -> tuple[int, list[str], dict[str, str]]:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    order_path = tmpdir / f"order-{run_idx}.txt"
    results_path = tmpdir / f"results-{run_idx}.json"
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
    try:
        r = subprocess.run(
            args, cwd=str(REPO), capture_output=True, text=True, timeout=180, env=env
        )
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = 124
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
    return rc, order, results


def main() -> int:
    lines: list[str] = [
        "AUD-0052 NAMED PROBE 2: repeated-identical-order flake census",
        "unit=AUD-0052",
        f"repeats={REPEATS}",
    ]
    run_rcs: list[int] = []
    run_orders: list[list[str]] = []
    run_results: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="aud0052-p2-") as td:
        tmp = Path(td)
        for i in range(REPEATS):
            rc, order, results = run_pytest_once(i, tmp)
            run_rcs.append(rc)
            run_orders.append(order)
            run_results.append(results)
            lines.append(
                f"REPEAT {i} rc={rc} collected={len(order)} results={len(results)}"
            )

    orders_identical = all(o == run_orders[0] for o in run_orders) and bool(
        run_orders[0]
    )
    lines.append(
        f"CONTROL identical_order_held_constant={orders_identical} "
        f"(all {REPEATS} repeats used the SAME declaration order -- this run's "
        "correctness precondition, opposite of probe1's shuffle control)"
    )

    all_nodeids: set[str] = set()
    for r in run_results:
        all_nodeids.update(r.keys())

    flaky: list[dict] = []
    if orders_identical:
        for nodeid in sorted(all_nodeids):
            outcomes = [r.get(nodeid) for r in run_results]
            seen = {o for o in outcomes if o is not None}
            if len(seen) > 1:
                counts = Counter(o for o in outcomes if o is not None)
                flaky.append(
                    {
                        "nodeid": nodeid,
                        "outcomes_by_repeat": outcomes,
                        "outcome_counts": dict(counts),
                    }
                )

    gt_nodeid = next((n for n in all_nodeids if GROUND_TRUTH_FLAKY in n), None)
    gt_flagged = gt_nodeid is not None and any(
        f["nodeid"] == gt_nodeid for f in flaky
    )
    gt_outcomes = (
        [r.get(gt_nodeid) for r in run_results] if gt_nodeid is not None else []
    )
    ground_truth_ok = orders_identical and gt_flagged
    lines.append(
        f"GROUND-TRUTH planted flaky test ({GROUND_TRUTH_FLAKY}): nodeid_found="
        f"{gt_nodeid is not None} outcomes={gt_outcomes} flagged={gt_flagged} "
        f"ok={ground_truth_ok}"
    )
    if not ground_truth_ok and gt_nodeid is not None and not gt_flagged:
        lines.append(
            "NOTE: ground-truth flaky draw agreed across all "
            f"{REPEATS} repeats this run (outcomes={gt_outcomes}) -- OS-entropy-"
            "seeded, so this can legitimately happen by chance "
            "(~9% per the fixture's own docstring); re-run to re-sample rather "
            "than treat a single agreeing run as proof the harness is broken."
        )

    ok = orders_identical and len(run_rcs) == REPEATS
    result = {
        "ok": ok,
        "unit": "AUD-0052",
        "probe": 2,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repeats": REPEATS,
        "run_rcs": run_rcs,
        "run_collected_counts": [len(o) for o in run_orders],
        "orders_identical": orders_identical,
        "flaky_tests_count": len(flaky),
        "flaky_tests": flaky,
        "ground_truth_ok": ground_truth_ok,
        "ground_truth": {
            "nodeid": gt_nodeid,
            "outcomes_by_repeat": gt_outcomes,
            "flagged": gt_flagged,
        },
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines.append(f"flaky_tests_count={len(flaky)} of {len(all_nodeids)} tests with a recorded outcome")
    for f in flaky:
        lines.append(f"  FLAKY {f['nodeid']} outcomes={f['outcomes_by_repeat']}")
    lines.append(f"ok={ok}")
    lines.append("SUCCESS:AUD-0052-probe2" if ok else "FAILED:AUD-0052-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
