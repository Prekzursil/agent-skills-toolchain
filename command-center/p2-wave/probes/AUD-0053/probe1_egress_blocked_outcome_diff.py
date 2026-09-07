#!/usr/bin/env python3
"""AUD-0053 NAMED PROBE 1: network-egress dependency census via blocked-run outcome diff.

Catalog evidence_requirement Probe 1: "run the suite with egress blocked and
record every test that changes outcome." Catalog tests_required (both-states
control): "the blocked environment must be proven to block -- assert that a
deliberate fetch fails inside it before trusting any test that passes there."

Method:
  1. BOTH-STATES CONTROL (tests_required, run FIRST and gates everything
     below): in THIS process, directly call fixtures/egress_block.py's
     install()/uninstall() around a real TCP connect() to example.com:80.
     GOOD_STATE (unblocked): the connect must SUCCEED. BAD_STATE (blocked):
     the SAME connect must FAIL with OSError. If either half fails, the rest
     of this probe's "blocked run found nothing" result would be
     meaningless (it could mean the block never engaged, not that nothing is
     network-dependent) -- so this is a hard gate, not an FYI.
  2. Run the full collectible test set (fixtures/collectible_scope.py, 138
     tests + this unit's 2 ground-truth fixtures = 140) once unblocked --
     the baseline.
  3. Run the SAME set again with fixtures/aud0053_plugin.py's
     --aud0053-block-egress flag, which installs the socket-level block in
     pytest_configure (before collection starts, so import-time network
     calls are covered too).
  4. network_dependent_candidates = tests that PASSED in the unblocked
     baseline but did NOT pass (failed or errored) in the blocked run --
     "tests that changed outcome," per the catalog's own wording.
  5. Ground truth: fixtures/network_dependent/test_network_ground_truth.py
     makes a real fetch it asserts on (must be caught: PASS->FAIL).
     test_network_ground_truth_silent.py makes the same fetch but swallows
     failure (must NOT be caught by outcome-diff -- that gap is exactly
     probe2's job, and is asserted here as a control on this probe's own
     boundary, not a defect in it).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
FIXTURES = PROBE / "fixtures"
OUT = PROBE / "probe1-egress-blocked-outcome-diff.json"
RAW = PROBE / "probe1-egress-blocked-outcome-diff.raw.txt"

sys.path.insert(0, str(FIXTURES))
import egress_block  # noqa: E402

GROUND_TRUTH_A = "test_ground_truth_a_real_network_fetch_changes_outcome"
GROUND_TRUTH_B = "test_ground_truth_b_silent_network_touch_claims_hermetic"
PROBE_HOST = ("example.com", 80)


def target_args() -> list[str]:
    import collectible_scope  # noqa: E402

    return list(collectible_scope.TARGET_ARGS)


def both_states_control() -> dict:
    """tests_required: prove the block actually blocks before trusting anything
    that passes inside it. Runs a real connect() both unblocked and blocked, in
    THIS process, directly against fixtures/egress_block.py (not through pytest)."""
    good_ok = False
    good_error = None
    try:
        with socket.create_connection(PROBE_HOST, timeout=8):
            good_ok = True
    except OSError as e:  # noqa: BLE001
        good_error = f"{type(e).__name__}: {e}"

    egress_block.install()
    bad_blocked = False
    bad_error = None
    try:
        with socket.create_connection(PROBE_HOST, timeout=8):
            pass
        bad_blocked = False
    except OSError as e:  # noqa: BLE001
        bad_blocked = True
        bad_error = f"{type(e).__name__}: {e}"
    finally:
        egress_block.uninstall()

    return {
        "good_state_unblocked_connect_succeeded": good_ok,
        "good_state_error": good_error,
        "bad_state_blocked_connect_failed": bad_blocked,
        "bad_state_error": bad_error,
        "ok": good_ok and bad_blocked,
    }


def run_pytest(block: bool, tmpdir: Path) -> tuple[int, str, dict[str, str]]:
    results_path = tmpdir / f"results-{'blocked' if block else 'baseline'}.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(FIXTURES) + os.pathsep + env.get("PYTHONPATH", "")
    env["AUD0053_RESULTS_PATH"] = str(results_path)
    args = [
        sys.executable,
        "-m",
        "pytest",
        *target_args(),
        "-p",
        "aud0053_plugin",
        "-q",
        "--tb=line",
        "-p",
        "no:cacheprovider",
    ]
    if block:
        args.append("--aud0053-block-egress")
    try:
        r = subprocess.run(
            args, cwd=str(REPO), capture_output=True, text=True, timeout=300, env=env
        )
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired as e:
        rc, out = 124, f"TIMEOUT: {e}"
    results = (
        json.loads(results_path.read_text(encoding="utf-8"))
        if results_path.is_file()
        else {}
    )
    return rc, out, results


def main() -> int:
    lines: list[str] = [
        "AUD-0053 NAMED PROBE 1: egress-blocked outcome-diff census",
        "unit=AUD-0053",
    ]

    control = both_states_control()
    lines.append(
        f"BOTH-STATES-CONTROL good_state(unblocked connect to {PROBE_HOST!r})="
        f"{control['good_state_unblocked_connect_succeeded']} "
        f"bad_state(blocked connect to {PROBE_HOST!r} fails)="
        f"{control['bad_state_blocked_connect_failed']} "
        f"bad_state_error={control['bad_state_error']!r} ok={control['ok']}"
    )

    if not control["ok"]:
        lines.append(
            "ABORT: both-states control failed -- refusing to trust any blocked-run "
            "result until a deliberate fetch is proven to fail inside the block "
            "AND succeed outside it"
        )
        RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = {
            "ok": False,
            "unit": "AUD-0053",
            "probe": 1,
            "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "both_states_control": control,
            "aborted_before_suite_run": True,
        }
        OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(RAW.read_text(encoding="utf-8"))
        return 1

    with tempfile.TemporaryDirectory(prefix="aud0053-p1-") as td:
        tmp = Path(td)

        base_rc, base_out, base_results = run_pytest(False, tmp)
        lines.append(
            f"BASELINE(unblocked) rc={base_rc} collected_results={len(base_results)}"
        )
        base_tail = "\n".join(base_out.splitlines()[-15:])
        lines.append(f"BASELINE tail:\n{base_tail}")

        blocked_rc, blocked_out, blocked_results = run_pytest(True, tmp)
        lines.append(
            f"BLOCKED(egress-block active) rc={blocked_rc} "
            f"collected_results={len(blocked_results)}"
        )
        blocked_tail = "\n".join(blocked_out.splitlines()[-15:])
        lines.append(f"BLOCKED tail:\n{blocked_tail}")

    baseline_collected = len(base_results)

    network_dependent_candidates: list[dict] = []
    for nodeid, base_outcome in base_results.items():
        if base_outcome != "passed":
            continue
        blocked_outcome = blocked_results.get(nodeid)
        if blocked_outcome is not None and blocked_outcome != "passed":
            network_dependent_candidates.append(
                {
                    "nodeid": nodeid,
                    "baseline_outcome": base_outcome,
                    "blocked_outcome": blocked_outcome,
                }
            )

    gt_a_nodeid = next((nid for nid in base_results if GROUND_TRUTH_A in nid), None)
    gt_a_caught = any(GROUND_TRUTH_A in c["nodeid"] for c in network_dependent_candidates)
    gt_a_baseline_passed = base_results.get(gt_a_nodeid) == "passed" if gt_a_nodeid else False

    gt_b_nodeid = next((nid for nid in base_results if GROUND_TRUTH_B in nid), None)
    gt_b_baseline_passed = base_results.get(gt_b_nodeid) == "passed" if gt_b_nodeid else False
    gt_b_blocked_passed = blocked_results.get(gt_b_nodeid) == "passed" if gt_b_nodeid else False
    gt_b_correctly_missed_by_outcome_diff = (
        gt_b_nodeid is not None
        and gt_b_baseline_passed
        and gt_b_blocked_passed
        and not any(GROUND_TRUTH_B in c["nodeid"] for c in network_dependent_candidates)
    )

    ground_truth_ok = (
        gt_a_nodeid is not None
        and gt_a_baseline_passed
        and gt_a_caught
        and gt_b_correctly_missed_by_outcome_diff
    )
    lines.append(
        f"GROUND-TRUTH-A (real network dependency) nodeid_found={gt_a_nodeid is not None} "
        f"baseline_passed={gt_a_baseline_passed} caught_by_outcome_diff={gt_a_caught}"
    )
    lines.append(
        f"GROUND-TRUTH-B (silent network touch, outcome-invariant) "
        f"nodeid_found={gt_b_nodeid is not None} baseline_passed={gt_b_baseline_passed} "
        f"blocked_passed={gt_b_blocked_passed} "
        f"correctly_missed_by_outcome_diff={gt_b_correctly_missed_by_outcome_diff} "
        "(this is the documented boundary of outcome-diff detection, not a defect -- "
        "probe2's socket trace is the instrument that catches this shape)"
    )

    ok = control["ok"] and base_rc in (0, 1) and ground_truth_ok
    result = {
        "ok": ok,
        "unit": "AUD-0053",
        "probe": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "both_states_control": control,
        "baseline_rc": base_rc,
        "blocked_rc": blocked_rc,
        "baseline_collected_count": baseline_collected,
        "blocked_collected_count": len(blocked_results),
        "network_dependent_candidates_count": len(network_dependent_candidates),
        "network_dependent_candidates": network_dependent_candidates,
        "ground_truth_ok": ground_truth_ok,
        "ground_truth": {
            "a_real_dependency_caught": gt_a_caught,
            "a_nodeid": gt_a_nodeid,
            "b_silent_touch_nodeid": gt_b_nodeid,
            "b_correctly_missed_by_outcome_diff": gt_b_correctly_missed_by_outcome_diff,
        },
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines.append(
        f"network_dependent_candidates_count={len(network_dependent_candidates)} "
        f"of baseline_collected={baseline_collected}"
    )
    for c in network_dependent_candidates:
        lines.append(
            f"  NETWORK-DEP {c['nodeid']} baseline={c['baseline_outcome']} "
            f"blocked={c['blocked_outcome']}"
        )
    lines.append(f"ok={ok}")
    lines.append("SUCCESS:AUD-0053-probe1" if ok else "FAILED:AUD-0053-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
