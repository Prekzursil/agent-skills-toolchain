#!/usr/bin/env python3
"""AUD-0053 NAMED PROBE 2: socket-level destination-host trace on an unblocked run.

Catalog evidence_requirement Probe 2: "a socket-level trace on an unblocked
run naming the destination hosts -- the blocked run finds tests that DEPEND
on the network and the trace finds tests that merely TOUCH it."

Method:
  1. Run the full collectible test set (fixtures/collectible_scope.py) once,
     UNBLOCKED, with fixtures/aud0053_plugin.py's --aud0053-trace-egress
     flag. That flag wraps socket.socket.connect (pass-through, never
     raises) so every non-loopback connect() attempt is recorded as
     {nodeid, host, port} against whichever test is currently executing
     (bracketed by a pytest_runtest_protocol hookwrapper), then the real
     connect proceeds unmodified -- the run's PASS/FAIL outcomes are
     unaffected by tracing.
  2. network_touching_tests = the set of distinct nodeids that appear in the
     trace at all, regardless of whether their own outcome changed.
  3. Cross-reference against probe1 (the catalog's own point, restated as
     this probe's control): every nodeid in probe1's
     network_dependent_candidates (outcome CHANGED under block) must also
     appear here (this trace is a superset -- you cannot depend on the
     network without touching it). test_ground_truth_b_silent_network_touch
     (outcome-invariant) must ALSO appear here even though probe1 could not
     see it -- that is the exact "touch vs depend" gap the catalog names,
     and this probe control asserts it is closed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
FIXTURES = PROBE / "fixtures"
OUT = PROBE / "probe2-socket-trace-destinations.json"
RAW = PROBE / "probe2-socket-trace-destinations.raw.txt"
PROBE1_OUT = PROBE / "probe1-egress-blocked-outcome-diff.json"

GROUND_TRUTH_A = "test_ground_truth_a_real_network_fetch_changes_outcome"
GROUND_TRUTH_B = "test_ground_truth_b_silent_network_touch_claims_hermetic"


def target_args() -> list[str]:
    sys.path.insert(0, str(FIXTURES))
    import collectible_scope  # noqa: E402

    return list(collectible_scope.TARGET_ARGS)


def main() -> int:
    lines: list[str] = [
        "AUD-0053 NAMED PROBE 2: socket-level destination-host trace",
        "unit=AUD-0053",
    ]

    results_path = REPO / "command-center/p2-wave/probes/AUD-0053/_p2_scratch_results.json"
    conns_path = REPO / "command-center/p2-wave/probes/AUD-0053/_p2_scratch_conns.json"
    for p in (results_path, conns_path):
        if p.exists():
            p.unlink()

    env = dict(os.environ)
    env["PYTHONPATH"] = str(FIXTURES) + os.pathsep + env.get("PYTHONPATH", "")
    env["AUD0053_RESULTS_PATH"] = str(results_path)
    env["AUD0053_CONNECTIONS_PATH"] = str(conns_path)
    args = [
        sys.executable,
        "-m",
        "pytest",
        *target_args(),
        "-p",
        "aud0053_plugin",
        "-q",
        "--tb=no",
        "-p",
        "no:cacheprovider",
        "--aud0053-trace-egress",
    ]
    try:
        r = subprocess.run(
            args, cwd=str(REPO), capture_output=True, text=True, timeout=300, env=env
        )
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired as e:
        rc, out = 124, f"TIMEOUT: {e}"

    tail = "\n".join(out.splitlines()[-15:])
    lines.append(f"TRACED-UNBLOCKED-RUN rc={rc}")
    lines.append(f"tail:\n{tail}")

    connections: list[dict] = (
        json.loads(conns_path.read_text(encoding="utf-8")) if conns_path.is_file() else []
    )
    results: dict[str, str] = (
        json.loads(results_path.read_text(encoding="utf-8"))
        if results_path.is_file()
        else {}
    )
    for p in (results_path, conns_path):
        if p.exists():
            p.unlink()

    by_nodeid: dict[str, list[dict]] = {}
    for c in connections:
        by_nodeid.setdefault(c.get("nodeid") or "<unknown>", []).append(
            {"host": c.get("host"), "port": c.get("port")}
        )

    distinct_hosts = sorted({c.get("host") for c in connections if c.get("host")})
    network_touching_tests = sorted(by_nodeid.keys())
    lines.append(
        f"collected_results={len(results)} distinct_hosts={distinct_hosts} "
        f"network_touching_tests_count={len(network_touching_tests)}"
    )
    for nid, dests in by_nodeid.items():
        lines.append(f"  TOUCH {nid} -> {dests}")

    gt_a_nodeid = next((nid for nid in results if GROUND_TRUTH_A in nid), None)
    gt_b_nodeid = next((nid for nid in results if GROUND_TRUTH_B in nid), None)
    gt_a_traced = gt_a_nodeid in by_nodeid if gt_a_nodeid else False
    gt_b_traced = gt_b_nodeid in by_nodeid if gt_b_nodeid else False
    ground_truth_ok = gt_a_traced and gt_b_traced
    lines.append(
        f"GROUND-TRUTH-A traced={gt_a_traced} GROUND-TRUTH-B(silent-touch) traced={gt_b_traced} "
        f"(both must be traced -- A depends on the network AND touches it, B only touches it; "
        "this trace is the instrument that can see B, unlike probe1's outcome-diff)"
    )

    # Cross-reference control: probe1's outcome-changed set must be a SUBSET of
    # this trace's touched set (you cannot depend on the network without
    # touching it -- if probe1 found a dependency this trace missed, either
    # probe would be broken).
    cross_ref_ok = None
    cross_ref_missing: list[str] = []
    if PROBE1_OUT.is_file():
        p1 = json.loads(PROBE1_OUT.read_text(encoding="utf-8"))
        p1_ids = {c["nodeid"] for c in p1.get("network_dependent_candidates", [])}
        cross_ref_missing = sorted(p1_ids - set(by_nodeid.keys()))
        cross_ref_ok = len(cross_ref_missing) == 0
        lines.append(
            f"CROSS-REFERENCE probe1_dependent_count={len(p1_ids)} "
            f"all_present_in_this_trace={cross_ref_ok} missing={cross_ref_missing}"
        )
    else:
        lines.append("CROSS-REFERENCE probe1 output not found (run probe1 first)")

    ok = ground_truth_ok and (cross_ref_ok is not False)
    result = {
        "ok": ok,
        "unit": "AUD-0053",
        "probe": 2,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "traced_run_rc": rc,
        "collected_results_count": len(results),
        "distinct_hosts": distinct_hosts,
        "network_touching_tests_count": len(network_touching_tests),
        "network_touching_tests": network_touching_tests,
        "connections_by_nodeid": by_nodeid,
        "ground_truth_ok": ground_truth_ok,
        "ground_truth": {
            "a_nodeid": gt_a_nodeid,
            "a_traced": gt_a_traced,
            "b_silent_touch_nodeid": gt_b_nodeid,
            "b_traced": gt_b_traced,
        },
        "cross_reference_ok": cross_ref_ok,
        "cross_reference_missing_from_trace": cross_ref_missing,
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines.append(f"ok={ok}")
    lines.append("SUCCESS:AUD-0053-probe2" if ok else "FAILED:AUD-0053-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
